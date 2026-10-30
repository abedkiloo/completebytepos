"""Sale rollback is Admin/Super Admin only; managers restore with Unvoid."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SUPER_ADMIN, ensure_permissions
from products.models import Category, Product
from sales.models import Sale, SaleItem, SaleRefund
from settings.test_utils import disable_maker_checker
from utils.tests.api_test_base import ManagerAPITestCase


class SaleRollbackAdminOnlyAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        disable_maker_checker()
        ensure_permissions()
        # Even with the checkbox, managers may not roll back — admin only.
        perm = Permission.objects.get(module='sales', action='rollback')
        Role.objects.get(name=ROLE_MANAGER).permissions.add(perm)
        cls.cat = Category.objects.create(name='RbApprCat', is_active=True)
        cls.product = Product.objects.create(
            name='Rb Appr Item',
            sku='RB-APPR-1',
            category=cls.cat,
            price=Decimal('20'),
            stock_quantity=6,
            track_stock=True,
            is_active=True,
        )
        cls.sale = Sale.objects.create(
            sale_number='S-RB-APPR',
            status='completed',
            subtotal=Decimal('40'),
            total=Decimal('40'),
            payment_method='cash',
            amount_paid=Decimal('40'),
            cashier=cls.manager_user,
        )
        SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            quantity=2,
            unit_price=Decimal('20'),
            subtotal=Decimal('40'),
        )

    def test_manager_cannot_rollback_even_with_permission(self):
        stock_before = self.product.stock_quantity
        resp = self.client.post(
            f'/api/sales/{self.sale.id}/rollback/',
            {'reason': 'Wrong till'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, resp.data)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'none')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, stock_before)
        self.assertFalse(SaleRefund.objects.filter(sale=self.sale).exists())

    def test_super_admin_applies_rollback_immediately(self):
        stock_before = self.product.stock_quantity
        admin = User.objects.create_superuser(
            'rb_admin', email='rb@test.com', password='x'
        )
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
            f'/api/sales/{self.sale.id}/rollback/',
            {'reason': 'Duplicate checkout'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.sale.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'refunded')
        self.assertEqual(self.product.stock_quantity, stock_before + 2)
        refund = SaleRefund.objects.get(sale=self.sale)
        self.assertEqual(refund.refund_type, 'rollback')
