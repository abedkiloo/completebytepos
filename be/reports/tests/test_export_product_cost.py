"""Admin Excel product-cost helpers and sales workbook cost columns."""

from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.test import RequestFactory
from openpyxl import load_workbook
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES, ROLE_SUPER_ADMIN, ensure_permissions, sync_default_roles
from reports.export_product_cost import (
    should_preserve_product_cost_on_export,
    user_may_export_product_cost,
)
from reports.sales_export import maybe_export_sales_workbook, render_sales_xlsx
from utils.tests.api_test_base import ManagerAPITestCase


class ExportProductCostTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ensure_permissions()
        sync_default_roles()

    def test_user_may_export_product_cost_admin_only(self):
        self.assertFalse(user_may_export_product_cost(None))
        self.assertFalse(user_may_export_product_cost(self.manager_user))

        admin = User.objects.create_user('cost_admin', password='x', is_staff=True)
        UserProfile.objects.create(
            user=admin,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        self.assertTrue(user_may_export_product_cost(admin))

        sales = User.objects.create_user('cost_sales', password='x')
        UserProfile.objects.create(
            user=sales,
            role='sales',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        self.assertFalse(user_may_export_product_cost(sales))

    def test_preserve_cost_only_on_admin_file_export(self):
        factory = RequestFactory()
        admin = User.objects.create_user('preserve_admin', password='x', is_staff=True)
        UserProfile.objects.create(
            user=admin,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        bare = factory.get('/r')
        bare.user = admin
        bare.query_params = bare.GET
        self.assertFalse(should_preserve_product_cost_on_export(bare))

        xlsx = factory.get('/r', {'format': 'xlsx'})
        xlsx.user = admin
        xlsx.query_params = xlsx.GET
        self.assertTrue(should_preserve_product_cost_on_export(xlsx))

        mgr = factory.get('/r', {'format': 'xlsx'})
        mgr.user = self.manager_user
        mgr.query_params = mgr.GET
        self.assertFalse(should_preserve_product_cost_on_export(mgr))

    def test_sales_xlsx_includes_cost_for_admin_only(self):
        payload = {
            'by_payment_method': [{'method': 'cash', 'count': 1, 'total': 100}],
            'by_product': [
                {
                    'product': 'Widget',
                    'sku': 'W1',
                    'category': 'A',
                    'quantity_sold': 2,
                    'revenue': 100,
                    'cogs': 40,
                    'gross_profit': 60,
                    'margin_pct': 60,
                    'sale_line_count': 1,
                }
            ],
            'sale_lines': [
                {
                    'sale_number': 'S-1',
                    'sale_date': '2026-11-06T10:00:00',
                    'product': 'Widget',
                    'sku': 'W1',
                    'quantity': 2,
                    'unit_price': 50,
                    'line_sale': 100,
                    'unit_cost': 20,
                    'line_cogs': 40,
                    'line_gross_profit': 60,
                }
            ],
            'summary': {'sales_count': 1, 'total_revenue': 100},
        }
        with_cost = render_sales_xlsx(payload, include_cost=True)
        wb = load_workbook(BytesIO(with_cost), data_only=True)
        self.assertIn('COGS', [c.value for c in wb['Goods Sold'][1]])
        self.assertIn('Unit cost', [c.value for c in wb['Sale Lines'][1]])

        without = render_sales_xlsx(payload, include_cost=False)
        wb2 = load_workbook(BytesIO(without), data_only=True)
        self.assertNotIn('COGS', [c.value for c in wb2['Goods Sold'][1]])
        self.assertNotIn('Unit cost', [c.value for c in wb2['Sale Lines'][1]])

        factory = RequestFactory()
        admin = User.objects.create_user('xlsx_admin', password='x', is_staff=True)
        UserProfile.objects.create(
            user=admin,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        req = factory.get('/sales', {'format': 'xlsx'})
        req.user = admin
        req.query_params = req.GET
        resp = maybe_export_sales_workbook(req, payload)
        self.assertIsNotNone(resp)
        self.assertEqual(resp['X-Report-Export'], 'xlsx')
        wb3 = load_workbook(BytesIO(resp.content), data_only=True)
        self.assertIn('COGS', [c.value for c in wb3['Goods Sold'][1]])
