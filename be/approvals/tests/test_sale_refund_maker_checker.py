"""Void/refund is Admin/Super Admin only; managers restore mistaken voids with Unvoid."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SUPER_ADMIN, sync_default_roles
from approvals.registry import ACTION_SALE_REFUND
from products.models import Category, Product
from sales.models import Sale, SaleItem, SaleRefund
from settings.test_utils import disable_maker_checker
from utils.tests.api_test_base import ManagerAPITestCase


class SaleRefundAdminOnlyAPITests(ManagerAPITestCase):
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
        disable_maker_checker()
        self.stock_before = self.product.stock_quantity

    def test_manager_cannot_void(self):
        resp = self.client.post(
            f'/api/sales/{self.sale.id}/refund/',
            {'reason': 'Customer changed mind', 'full': True},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, resp.data)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'none')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, self.stock_before)
        self.assertFalse(SaleRefund.objects.filter(sale=self.sale).exists())

    def test_manager_cannot_check_refund_action(self):
        from approvals.permissions import user_can_check

        self.assertFalse(user_can_check(self.manager_user, ACTION_SALE_REFUND))

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
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, self.stock_before + 2)
        self.assertTrue(SaleRefund.objects.filter(sale=self.sale).exists())
