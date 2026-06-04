"""
Contract: every material write path leaves an append-only AuditLog row.

Tests are written first — implementations must satisfy these expectations.
"""

from decimal import Decimal

from django.contrib.auth.models import User

from accounts.models import AuditLog, Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, sync_default_roles
from products.models import Category, Product
from sales.models import Customer, Sale
from settings.models import Branch, ModuleSettings, Tenant
from utils.tests.api_test_base import ManagerAPITestCase, SuperAdminAPITestCase


def _audit_count(**filters):
    return AuditLog.objects.filter(**filters).count()


class AuditTrailContractTests(ManagerAPITestCase):
    """Manager persona can exercise most write modules."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = Category.objects.create(name='Audit Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Audit Product',
            sku='AUD-PROD-1',
            category=cls.category,
            price=Decimal('100'),
            cost=Decimal('50'),
            stock_quantity=50,
            track_stock=True,
            is_active=True,
        )
        cls.tenant, cls.branch, _ = cls.create_tenant_with_branches(cls.manager_user)

    def setUp(self):
        super().setUp()
        self.set_session_branch(self.tenant, self.branch)
        AuditLog.objects.all().delete()

    def test_category_create_is_audited(self):
        response = self.client.post(
            '/api/products/categories/',
            {'name': 'Audit Subcat', 'is_active': True},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertGreaterEqual(
            _audit_count(action='create', module='categories'),
            1,
        )

    def test_product_update_is_audited(self):
        response = self.client.patch(
            f'/api/products/{self.product.id}/',
            {'name': 'Audit Product Renamed'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertGreaterEqual(
            _audit_count(action='update', module='products'),
            1,
        )

    def test_customer_create_is_audited(self):
        response = self.client.post(
            '/api/sales/customers/',
            {
                'name': 'Audit Customer',
                'phone': '0700111222',
                'customer_type': 'individual',
                'is_active': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertGreaterEqual(
            _audit_count(action='create', module='customers'),
            1,
        )

    def test_stock_adjust_is_audited(self):
        response = self.client.post(
            '/api/inventory/adjust/',
            {
                'product_id': self.product.id,
                'quantity': 3,
                'notes': 'audit test adjust',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertGreaterEqual(
            _audit_count(module='inventory'),
            1,
        )

    def test_stock_purchase_is_audited(self):
        response = self.client.post(
            '/api/inventory/purchase/',
            {
                'product_id': self.product.id,
                'quantity': 2,
                'unit_cost': '45.00',
                'notes': 'audit purchase',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(
            AuditLog.objects.filter(module='inventory', action='stock_purchase').exists()
            or AuditLog.objects.filter(module='inventory').exclude(action='create').exists()
        )

    def test_expense_create_and_approve_are_audited(self):
        create_resp = self.client.post(
            '/api/expenses/',
            {
                'description': 'Audit expense',
                'amount': '25.00',
                'expense_date': '2026-06-01',
                'payment_method': 'cash',
            },
            format='json',
        )
        self.assertEqual(create_resp.status_code, 201, create_resp.data)
        self.assertGreaterEqual(_audit_count(module='expenses', action='create'), 1)

        expense_id = create_resp.data['id']
        approve_resp = self.client.post(f'/api/expenses/{expense_id}/approve/')
        self.assertEqual(approve_resp.status_code, 200, approve_resp.data)
        self.assertTrue(
            AuditLog.objects.filter(module='expenses', action='approve').exists()
        )

    def test_holding_save_and_checkout_are_audited(self):
        hold_resp = self.client.post(
            '/api/sales/holding/',
            {
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 1,
                        'unit_price': '100.00',
                    }
                ],
                'tax_amount': '0',
                'discount_amount': '0',
            },
            format='json',
        )
        self.assertEqual(hold_resp.status_code, 200, hold_resp.data)
        self.assertTrue(
            AuditLog.objects.filter(module='sales', action='holding_save').exists()
        )

        holding_id = hold_resp.data['id']
        checkout_resp = self.client.post(
            f'/api/sales/{holding_id}/checkout/',
            {
                'payment_method': 'cash',
                'amount_paid': '100.00',
                'allow_partial_payment': False,
            },
            format='json',
        )
        self.assertEqual(checkout_resp.status_code, 200, checkout_resp.data)
        self.assertGreaterEqual(
            _audit_count(module='sales', action='checkout'),
            1,
        )


class AuditTrailAuthTests(SuperAdminAPITestCase):
    def test_login_and_logout_write_audit_rows(self):
        AuditLog.objects.all().delete()
        login_resp = self.client.post(
            '/api/accounts/auth/login/',
            {'username': 'phase2_admin', 'password': 'admin123'},
            format='json',
        )
        self.assertEqual(login_resp.status_code, 200)
        self.assertGreaterEqual(_audit_count(action='login'), 1)

        logout_resp = self.client.post(
            '/api/accounts/auth/logout/',
            {'refresh': login_resp.data.get('refresh', '')},
            format='json',
        )
        self.assertEqual(logout_resp.status_code, 200)
        self.assertGreaterEqual(_audit_count(action='logout'), 1)


class AuditTrailSupplierTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ModuleSettings.objects.update_or_create(
            module_name='suppliers',
            defaults={'description': 'suppliers', 'is_enabled': True},
        )

    def setUp(self):
        super().setUp()
        AuditLog.objects.all().delete()

    def test_supplier_create_is_audited(self):
        response = self.client.post(
            '/api/suppliers/suppliers/',
            {
                'name': 'Audit Supplier Ltd',
                'phone': '0700999888',
                'is_active': True,
            },
            format='json',
        )
        self.assertIn(response.status_code, (200, 201), response.data)
        self.assertGreaterEqual(
            _audit_count(module='suppliers', action='create'),
            1,
        )
