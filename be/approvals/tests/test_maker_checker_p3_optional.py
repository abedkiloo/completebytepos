"""
P3 optional: post-completion sale edits (off by default).

POS checkout and create are unchanged. Refunds/promotions/discount MC are deferred.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SUPER_ADMIN, sync_default_roles
from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_COMPLETED_EDIT
from approvals.tests.test_maker_checker import _enable_maker_checker
from sales.models import Sale
from settings.models import StoreSettings
from utils.tests.api_test_base import ManagerAPITestCase, SuperAdminAPITestCase


def _enable_sales_controls(enabled=True):
    store = StoreSettings.load()
    store.maker_checker_sales_controls = enabled
    store.save(update_fields=['maker_checker_sales_controls'])
    store.refresh_from_db()


class MakerCheckerP3OptionalTests(SuperAdminAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_default_roles()
        cls.checker = User.objects.create_user('p3_chk', password='x', is_staff=True)
        UserProfile.objects.create(
            user=cls.checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        cls.sale = Sale.objects.create(
            sale_number='P3-SALE-1',
            total=Decimal('250'),
            subtotal=Decimal('250'),
            status='completed',
            payment_method='cash',
            amount_paid=Decimal('250'),
            notes='Original note',
        )

    def setUp(self):
        super().setUp()
        _enable_maker_checker(enabled=True)
        _enable_sales_controls(enabled=False)
        PendingChange.objects.all().delete()

    def _checker_client(self):
        client = self.client.__class__()
        token = RefreshToken.for_user(self.checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def test_completed_sale_patch_blocked_when_optional_off(self):
        resp = self.client.patch(
            f'/api/sales/{self.sale.id}/',
            {'notes': 'Should not apply'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.notes, 'Original note')

    def test_completed_sale_total_unchanged_after_pending_product_price(self):
        """Reports/history: existing sale total is not rewritten by catalog MC (row 35)."""
        from products.models import Category, Product

        cat = Category.objects.create(name='P3Cat', is_active=True)
        product = Product.objects.create(
            name='P3 Prod',
            sku='P3-1',
            category=cat,
            price=Decimal('100'),
            stock_quantity=5,
            is_active=True,
        )
        self.client.patch(
            f'/api/products/{product.id}/',
            {'price': '999.00', 'reason': 'Must not touch completed sale'},
            format='json',
        )
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.total, Decimal('250'))

    def test_optional_notes_edit_pending_then_approve(self):
        _enable_sales_controls(enabled=True)
        resp = self.client.patch(
            f'/api/sales/{self.sale.id}/',
            {'notes': 'Corrected receipt note', 'reason': 'Customer request'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.notes, 'Original note')

        change = PendingChange.objects.get(action_type=ACTION_SALE_COMPLETED_EDIT)
        approve = self._checker_client().post(
            f'/api/approvals/pending-changes/{change.id}/approve/',
            {},
            format='json',
        )
        self.assertEqual(approve.status_code, status.HTTP_200_OK)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.notes, 'Corrected receipt note')
        self.assertEqual(self.sale.total, Decimal('250'))

    def test_optional_rejects_total_edit(self):
        _enable_sales_controls(enabled=True)
        resp = self.client.patch(
            f'/api/sales/{self.sale.id}/',
            {'total': '1.00', 'reason': 'Nope'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.total, Decimal('250'))


class MakerCheckerP3PolicyUnitTests(ManagerAPITestCase):
    def test_sales_policy_helpers(self):
        from approvals.sales_policy import (
            completed_sale_direct_edit_blocked,
            filter_queueable_sale_fields,
            is_sales_maker_checker_active,
            sale_edit_has_unsupported_fields,
        )

        _enable_maker_checker(enabled=True)
        _enable_sales_controls(enabled=False)
        self.assertFalse(is_sales_maker_checker_active())
        self.assertTrue(completed_sale_direct_edit_blocked())
        self.assertEqual(
            filter_queueable_sale_fields({'notes': 'a', 'total': '9'}),
            {'notes': 'a'},
        )
        self.assertTrue(sale_edit_has_unsupported_fields({'total': '9'}))
