"""Void/refund always queues for admin approval before stock and books change."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SUPER_ADMIN, sync_default_roles
from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_REFUND
from products.models import Category, Product
from sales.models import Sale, SaleItem, SaleRefund
from settings.test_utils import disable_maker_checker, enable_maker_checker
from utils.tests.api_test_base import ManagerAPITestCase


class SaleRefundAdminApprovalAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_default_roles()
        cls.cat = Category.objects.create(name='MC Ref', is_active=True)
        cls.product = Product.objects.create(
            name='MC Product',
            sku='MC-REF',
            category=cls.cat,
            price=Decimal('50'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )
        cls.sale = Sale.objects.create(
            sale_number='S-MC-REF',
            status='completed',
            subtotal=Decimal('100'),
            total=Decimal('100'),
            payment_method='cash',
            amount_paid=Decimal('100'),
            cashier=cls.manager_user,
        )
        cls.line = SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            quantity=2,
            unit_price=Decimal('50'),
            subtotal=Decimal('100'),
        )

    def setUp(self):
        super().setUp()
        # Void/refund must still queue when the global toggle is off.
        disable_maker_checker()
        self.stock_before = self.product.stock_quantity

    def test_refund_queues_even_when_maker_checker_off(self):
        resp = self.client.post(
            f'/api/sales/{self.sale.id}/refund/',
            {'reason': 'Customer changed mind', 'full': True},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.assertIn('pending_change', resp.data)
        change = PendingChange.objects.get(action_type=ACTION_SALE_REFUND)
        self.assertEqual(change.entity_id, str(self.sale.id))
        self.assertEqual(change.status, PendingChange.STATUS_PENDING)

        self.sale.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'none')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, self.stock_before)
        self.assertFalse(SaleRefund.objects.filter(sale=self.sale).exists())

    def test_refund_queues_when_maker_checker_on(self):
        enable_maker_checker()
        resp = self.client.post(
            f'/api/sales/{self.sale.id}/refund/',
            {'reason': 'Wrong item', 'full': True},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.assertTrue(PendingChange.objects.filter(action_type=ACTION_SALE_REFUND).exists())

    def test_maker_cannot_self_approve_refund(self):
        self.client.post(
            f'/api/sales/{self.sale.id}/refund/',
            {'reason': 'Wrong item', 'full': True},
            format='json',
        )
        change = PendingChange.objects.get(action_type=ACTION_SALE_REFUND)
        deny = self.client.post(f'/api/approvals/pending-changes/{change.id}/approve/')
        self.assertEqual(deny.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_approval_applies_refund(self):
        queued = self.client.post(
            f'/api/sales/{self.sale.id}/refund/',
            {'reason': 'Duplicate lines', 'full': True},
            format='json',
        )
        self.assertEqual(queued.status_code, status.HTTP_202_ACCEPTED, queued.data)
        change = PendingChange.objects.get(action_type=ACTION_SALE_REFUND)

        checker = User.objects.create_user('refund_checker', password='x', is_staff=True)
        UserProfile.objects.create(
            user=checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        checker_client = self.client.__class__()
        checker_token = RefreshToken.for_user(checker)
        checker_client.credentials(HTTP_AUTHORIZATION=f'Bearer {checker_token.access_token}')

        approved = checker_client.post(f'/api/approvals/pending-changes/{change.id}/approve/')
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.data)

        self.sale.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'refunded')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, self.stock_before + 2)
        self.assertTrue(SaleRefund.objects.filter(sale=self.sale).exists())

    def test_duplicate_pending_refund_blocked(self):
        first = self.client.post(
            f'/api/sales/{self.sale.id}/refund/',
            {'reason': 'First request', 'full': True},
            format='json',
        )
        self.assertEqual(first.status_code, status.HTTP_202_ACCEPTED)
        second = self.client.post(
            f'/api/sales/{self.sale.id}/refund/',
            {'reason': 'Second request', 'full': True},
            format='json',
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_super_admin_applies_refund_immediately(self):
        admin = User.objects.create_user('refund_admin', password='x', is_staff=True)
        UserProfile.objects.create(
            user=admin,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        admin_client = self.client.__class__()
        token = RefreshToken.for_user(admin)
        admin_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

        resp = admin_client.post(
            f'/api/sales/{self.sale.id}/refund/',
            {'reason': 'Admin void', 'full': True},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'refunded')
        self.assertFalse(PendingChange.objects.filter(action_type=ACTION_SALE_REFUND).exists())
