"""Draft saves must not turn one keyed quantity into double on the sale.

A cashier who keys 28 can have the draft sync and Checkout write that line at
the same time. Those two inserts used to both survive, and checkout then added
them into one line of 56.
"""

from decimal import Decimal
import threading
import time

from django.contrib.auth.models import User
from django.db import OperationalError, connection
from django.test import TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from products.models import Category, Product
from sales.models import Customer
from sales.services import SaleService
from settings.models import Branch, Tenant

VICTIM_PHONE = '254700111028'


class HoldingQuantityRaceTests(TransactionTestCase):
    """Overlapping draft saves keep the quantity the cashier keyed."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='qty_cashier',
            email='qty@test.com',
            password='admin123',
        )
        self.tenant = Tenant.objects.create(
            name='Qty Tenant',
            code='QTY',
            owner=self.user,
            created_by=self.user,
        )
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            branch_code='Q1',
            name='Qty Shop',
            created_by=self.user,
        )
        category = Category.objects.create(name='Stands', is_active=True)
        self.product = Product.objects.create(
            name='6 inch round stand',
            sku='STAND-28',
            category=category,
            mrp=Decimal('250.00'),
            price=Decimal('250.00'),
            cost=Decimal('100.00'),
            stock_quantity=400,
            track_stock=True,
            is_active=True,
        )
        self.customer = Customer.objects.create(
            name='Javala',
            phone=VICTIM_PHONE,
            is_active=True,
        )
        self.service = SaleService()
        self.holding = self.service.save_holding_sale(
            self.user,
            [{'product_id': self.product.id, 'quantity': 28, 'unit_price': '250.00'}],
            branch=self.branch,
            customer=self.customer,
        )

    def _save_once(self):
        """Save quantity 28, retrying when SQLite reports the table is locked.

        Postgres waits on the row lock. SQLite raises instead, so a retry
        runs after the other save commits and must replace the line, not add.
        """
        last_error = None
        for _ in range(12):
            try:
                self.service.save_holding_sale(
                    self.user,
                    [{
                        'product_id': self.product.id,
                        'quantity': 28,
                        'unit_price': '250.00',
                    }],
                    branch=self.branch,
                    customer=self.customer,
                    holding_id=self.holding.id,
                )
                return
            except OperationalError as exc:
                last_error = exc
                if 'locked' not in str(exc).lower():
                    raise
                connection.close()
                time.sleep(0.05)
        if last_error is not None:
            raise last_error

    def test_eight_overlapping_saves_keep_one_line_of_28(self):
        """Stress: eight draft saves at once still store quantity 28, not 224."""
        barrier = threading.Barrier(8)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=10)
                self._save_once()
            except Exception as exc:  # noqa: BLE001 — collected for the assertion
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(errors, [])
        lines = list(self.holding.items.all())
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].quantity, 28)
        self.assertNotIn(VICTIM_PHONE, str(lines[0]))

    def test_checkout_after_overlapping_saves_charges_28(self):
        """Corrected sale: checkout keeps 28 pieces at 250, total 7000."""
        barrier = threading.Barrier(2)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=10)
                self._save_once()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(errors, [])

        sale = self.service.complete_holding_sale(
            self.holding,
            payment_method='on_account',
            amount_paid=Decimal('0'),
            allow_partial=True,
            user=self.user,
            branch=self.branch,
        )
        sale.refresh_from_db()
        self.assertEqual(sale.items.count(), 1)
        self.assertEqual(sale.items.first().quantity, 28)
        self.assertEqual(sale.total, Decimal('7000.00'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 372)

    def test_other_cashier_cannot_rewrite_the_quantity(self):
        """Security: another user posting this draft id does not change 28."""
        other = User.objects.create_user(username='other_qty', password='other123')
        client = APIClient()
        refresh = RefreshToken.for_user(other)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        response = client.post(
            '/api/sales/holding/',
            {
                'holding_id': self.holding.id,
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 56,
                        'unit_price': '250.00',
                    }
                ],
                'customer_id': self.customer.id,
            },
            format='json',
        )
        body = str(response.data)
        self.assertNotIn(VICTIM_PHONE, body)
        self.holding.refresh_from_db()
        self.assertEqual(self.holding.items.count(), 1)
        self.assertEqual(self.holding.items.first().quantity, 28)
        if response.status_code == status.HTTP_200_OK:
            self.assertNotEqual(response.data.get('id'), self.holding.id)

    def test_anonymous_and_clerk_cannot_save_the_draft(self):
        """Security: no token is 401, and a user without sales.create is 403."""
        anon = APIClient()
        anon_response = anon.post(
            '/api/sales/holding/',
            {'holding_id': self.holding.id, 'items': []},
            format='json',
        )
        self.assertEqual(anon_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn(VICTIM_PHONE, str(anon_response.data))

        clerk = User.objects.create_user(username='qty_clerk', password='clerk123')
        client = APIClient()
        refresh = RefreshToken.for_user(clerk)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        denied = client.post(
            '/api/sales/holding/',
            {
                'holding_id': self.holding.id,
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 56,
                        'unit_price': '250.00',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(VICTIM_PHONE, str(denied.data))
        self.assertIn('sales.create', str(denied.data))
        self.holding.refresh_from_db()
        self.assertEqual(self.holding.items.first().quantity, 28)
