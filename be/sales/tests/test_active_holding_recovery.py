"""Active holding draft recovery for Terminal POS."""

from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from products.models import Category, Product
from sales.models import Sale
from sales.services import SaleService
from settings.models import Branch, Tenant
from settings.test_utils import disable_multi_branch_support


class ActiveHoldingRecoveryAPITestCase(APITestCase):
    def setUp(self):
        disable_multi_branch_support()
        self.user = User.objects.create_superuser(
            username='hold_recover',
            email='hold@test.com',
            password='admin123',
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        self.tenant = Tenant.objects.create(
            name='Recovery Tenant',
            code='REC',
            owner=self.user,
            created_by=self.user,
        )
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            branch_code='R1',
            name='Register',
            created_by=self.user,
        )
        category = Category.objects.create(name='Cat', is_active=True)
        self.product = Product.objects.create(
            name='Draft SKU',
            sku='DRF-001',
            category=category,
            price=Decimal('100'),
            cost=Decimal('50'),
            stock_quantity=20,
            is_active=True,
        )
        self.service = SaleService()

    def test_active_holding_returns_null_when_no_draft(self):
        response = self.client.get('/api/sales/active-holding/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data.get('holding'))

    def test_active_holding_returns_draft_with_items(self):
        holding = self.service.save_holding_sale(
            self.user,
            [
                {
                    'product_id': self.product.id,
                    'quantity': 2,
                    'unit_price': '100',
                }
            ],
            branch=None,
        )
        response = self.client.get('/api/sales/active-holding/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data['holding']
        self.assertIsNotNone(data)
        self.assertEqual(data['id'], holding.id)
        self.assertEqual(data['status'], 'holding')
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['items'][0]['quantity'], 2)

    def test_get_active_holding_service_scoped_to_cashier(self):
        other = User.objects.create_user(username='other_cashier', password='x')
        self.service.save_holding_sale(
            self.user,
            [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '100'}],
        )
        self.assertIsNone(self.service.get_active_holding(other))
        found = self.service.get_active_holding(self.user)
        self.assertIsNotNone(found)
        self.assertEqual(found.status, 'holding')

    def test_cancel_holding_clears_active_holding(self):
        holding = self.service.save_holding_sale(
            self.user,
            [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '100'}],
        )
        self.service.cancel_holding_sale(holding)
        response = self.client.get('/api/sales/active-holding/')
        self.assertIsNone(response.data.get('holding'))
        holding.refresh_from_db()
        self.assertEqual(holding.status, 'cancelled')

    def test_stale_holding_purged_after_12_hours(self):
        holding = self.service.save_holding_sale(
            self.user,
            [{'product_id': self.product.id, 'quantity': 2, 'unit_price': '100'}],
        )
        stale_time = timezone.now() - timedelta(hours=13)
        Sale.objects.filter(pk=holding.pk).update(updated_at=stale_time)
        purged = self.service.purge_stale_holdings(self.user)
        self.assertEqual(purged, 1)
        holding.refresh_from_db()
        self.assertEqual(holding.status, 'cancelled')
        response = self.client.get('/api/sales/active-holding/')
        self.assertIsNone(response.data.get('holding'))

    def test_login_purges_stale_holdings_for_user(self):
        holding = self.service.save_holding_sale(
            self.user,
            [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '100'}],
        )
        stale_time = timezone.now() - timedelta(hours=13)
        Sale.objects.filter(pk=holding.pk).update(updated_at=stale_time)

        login_response = self.client.post(
            '/api/accounts/auth/login/',
            {'username': 'hold_recover', 'password': 'admin123'},
            format='json',
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        holding.refresh_from_db()
        self.assertEqual(holding.status, 'cancelled')
