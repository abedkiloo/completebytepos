"""Admin-only sale rollback restores stock and posts balancing journals."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status

from accounts.models import Permission, Role
from accounts.role_definitions import ROLE_MANAGER, ensure_permissions
from inventory.models import StockMovement
from products.models import Category, Product
from sales.models import Sale, SaleItem
from sales.rollback import rollback_sale, sale_is_rollbackable
from settings.test_utils import disable_maker_checker
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase, SuperAdminAPITestCase


class SaleRollbackServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import User

        cls.user = User.objects.create_user('rb_admin', password='x')
        cls.cat = Category.objects.create(name='RbCat', is_active=True)
        cls.product = Product.objects.create(
            name='Rollback Item',
            sku='RB-1',
            category=cls.cat,
            price=Decimal('50'),
            stock_quantity=8,
            track_stock=True,
            is_active=True,
        )
        cls.sale = Sale.objects.create(
            sale_number='S-RB-1',
            status='completed',
            subtotal=Decimal('100'),
            total=Decimal('100'),
            payment_method='cash',
            amount_paid=Decimal('100'),
            cashier=cls.user,
        )
        SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            quantity=2,
            unit_price=Decimal('50'),
            subtotal=Decimal('100'),
        )

    def test_requires_reason(self):
        with self.assertRaises(ValidationError):
            rollback_sale(sale=self.sale, reason='', user=self.user)

    def test_rejects_non_completed(self):
        self.sale.status = 'holding'
        self.sale.save(update_fields=['status'])
        with self.assertRaises(ValidationError):
            rollback_sale(sale=self.sale, reason='mistake', user=self.user)

    def test_full_rollback_returns_stock_and_marks_refunded(self):
        stock_before = self.product.stock_quantity
        refund = rollback_sale(sale=self.sale, reason='wrong till', user=self.user)
        self.assertEqual(refund.refund_type, 'rollback')
        self.sale.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'refunded')
        self.assertEqual(self.product.stock_quantity, stock_before + 2)
        self.assertTrue(
            StockMovement.objects.filter(reference=refund.refund_number).exists()
        )
        self.assertFalse(sale_is_rollbackable(self.sale))
        with self.assertRaises(ValidationError):
            rollback_sale(sale=self.sale, reason='again', user=self.user)


class SaleRollbackAPITests(SuperAdminAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        disable_maker_checker()
        cls.cat = Category.objects.create(name='RbApiCat', is_active=True)
        cls.product = Product.objects.create(
            name='Rb Api Item',
            sku='RB-API-1',
            category=cls.cat,
            price=Decimal('20'),
            stock_quantity=5,
            track_stock=True,
            is_active=True,
        )
        cls.sale = Sale.objects.create(
            sale_number='S-RB-API',
            status='completed',
            subtotal=Decimal('40'),
            total=Decimal('40'),
            payment_method='cash',
            amount_paid=Decimal('40'),
            cashier=cls.admin,
        )
        SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            quantity=2,
            unit_price=Decimal('20'),
            subtotal=Decimal('40'),
        )

    def test_admin_can_rollback(self):
        resp = self.client.post(
            f'/api/sales/{self.sale.id}/rollback/',
            {'reason': 'Duplicate checkout'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['refund_type'], 'rollback')
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'refunded')
        self.assertTrue(self.client.get(f'/api/sales/{self.sale.id}/').data['can_rollback'] is False)

    def test_rollback_requires_reason(self):
        resp = self.client.post(
            f'/api/sales/{self.sale.id}/rollback/',
            {'reason': '  '},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class SaleRollbackPermissionTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        disable_maker_checker()
        cls.cat = Category.objects.create(name='RbMgrCat', is_active=True)
        cls.product = Product.objects.create(
            name='Rb Mgr Item',
            sku='RB-MGR-1',
            category=cls.cat,
            price=Decimal('10'),
            stock_quantity=3,
            track_stock=True,
            is_active=True,
        )
        cls.sale = Sale.objects.create(
            sale_number='S-RB-MGR',
            status='completed',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('10'),
            cashier=cls.manager_user,
        )
        SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            quantity=1,
            unit_price=Decimal('10'),
            subtotal=Decimal('10'),
        )

    def test_manager_denied_until_permission_checked(self):
        url = f'/api/sales/{self.sale.id}/rollback/'
        denied = self.client.post(url, {'reason': 'mistake'}, format='json')
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        ensure_permissions()
        perm = Permission.objects.get(module='sales', action='rollback')
        role = Role.objects.get(name=ROLE_MANAGER)
        role.permissions.add(perm)

        allowed = self.client.post(url, {'reason': 'mistake'}, format='json')
        self.assertEqual(allowed.status_code, status.HTTP_202_ACCEPTED, allowed.data)
        self.assertIn('pending_change', allowed.data)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'none')


class SaleRollbackSalesPersonaTests(SalesAPITestCase):
    def test_sales_persona_cannot_rollback(self):
        sale = Sale.objects.create(
            sale_number='S-RB-SALES',
            status='completed',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('10'),
            cashier=self.sales_user,
        )
        resp = self.client.post(
            f'/api/sales/{sale.id}/rollback/',
            {'reason': 'oops'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
