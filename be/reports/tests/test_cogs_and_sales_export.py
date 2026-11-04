"""Coverage for COGS / sales Excel builders and package gates."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SUPER_ADMIN, ensure_permissions, sync_default_roles
from products.models import Category, Product
from reports.cogs_export import (
    extract_cogs_payload,
    maybe_export_cogs_workbook,
    render_cogs_csv,
    render_cogs_xlsx,
)
from reports.module_settings import reports_action_enabled, reports_trading_profit_enabled
from reports.sales_export import (
    is_sales_export_payload,
    maybe_export_sales_workbook,
    render_sales_csv,
    render_sales_xlsx,
)
from reports.sale_scope import posted_sales
from reports.sales_goods import goods_sold_for_sales
from sales.models import Sale, SaleItem
from settings.models import ModuleFeature, ModuleSettings
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase


class CogsSalesExportUnitTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ensure_permissions()
        sync_default_roles()
        cls.cat = Category.objects.create(name='Export Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Export Item',
            sku='EXP-1',
            category=cls.cat,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )

    def _admin_client(self):
        admin = User.objects.create_user('export_admin', password='x', is_staff=True)
        UserProfile.objects.create(
            user=admin,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(admin)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def _sale(self):
        sale = Sale.objects.create(
            sale_number='S-EXP-1',
            status='completed',
            subtotal=Decimal('200'),
            total=Decimal('200'),
            tax_amount=Decimal('0'),
            payment_method='cash',
            amount_paid=Decimal('200'),
            cashier=self.manager_user,
            occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=2,
            unit_price=Decimal('100'),
            unit_cost=Decimal('40'),
            subtotal=Decimal('200'),
        )
        return sale

    def test_goods_sold_for_sales_aggregates_qty(self):
        self._sale()
        goods = goods_sold_for_sales(posted_sales())
        self.assertTrue(goods['by_product'])
        self.assertEqual(goods['by_product'][0]['product'], 'Export Item')
        self.assertEqual(goods['by_product'][0]['quantity_sold'], 2.0)
        self.assertEqual(len(goods['sale_lines']), 1)

    def test_cogs_workbook_sheets_and_extract(self):
        payload = {
            'period': 'month',
            'cogs_sold': 80.0,
            'cogs_refunded': 10.0,
            'cogs': 70.0,
            'sale_count': 1,
            'sales_shown': 1,
            'truncated': True,
            'cost_missing_sale_count': 1,
            'explanation': 'test',
            'formula': 'COGS sold − refunds',
            'title': 'COGS',
            'sales': [
                {
                    'sale_number': 'S-EXP-1',
                    'occurred_at': '2026-11-04T10:00:00',
                    'sale_total': 200.0,
                    'line_revenue': 200.0,
                    'revenue_gap': 0.0,
                    'cogs': 80.0,
                    'gross_profit': 120.0,
                    'margin_pct': 60.0,
                    'payment_method': 'cash',
                    'cashier': 'mgr',
                    'concerns': ['No cost on: Missing'],
                    'lines': [
                        {
                            'product_name': 'Export Item',
                            'sku': 'EXP-1',
                            'quantity': 2,
                            'unit_price': 100.0,
                            'line_sale': 200.0,
                            'unit_cost': 40.0,
                            'line_cogs': 80.0,
                            'line_gross_profit': 120.0,
                            'margin_pct': 60.0,
                            'source': 'unit_cost',
                            'cost_missing': False,
                        },
                        {
                            'product_name': 'Missing',
                            'sku': '',
                            'quantity': 1,
                            'unit_price': 10.0,
                            'line_sale': 10.0,
                            'unit_cost': 0,
                            'line_cogs': 0,
                            'line_gross_profit': 10.0,
                            'margin_pct': 100.0,
                            'source': 'unit_cost',
                            'cost_missing': True,
                        },
                        {
                            'product_name': 'Legacy stock movements (no line unit cost)',
                            'sku': '',
                            'quantity': None,
                            'unit_price': None,
                            'line_sale': None,
                            'unit_cost': None,
                            'line_cogs': 5.0,
                            'line_gross_profit': None,
                            'margin_pct': None,
                            'source': 'legacy_movement',
                            'cost_missing': False,
                        },
                    ],
                }
            ],
            'refunds': [
                {
                    'sale_number': 'S-EXP-1',
                    'created_at': '2026-11-04T12:00:00',
                    'refund_amount': 50.0,
                    'cogs_restored': 10.0,
                    'lines': [],
                },
                {
                    'sale_number': 'S-EXP-1',
                    'created_at': '2026-11-04T13:00:00',
                    'refund_amount': 20.0,
                    'cogs_restored': 8.0,
                    'lines': [
                        {
                            'product_name': 'Export Item',
                            'quantity': 1,
                            'unit_cost': 40.0,
                            'line_cogs': 40.0,
                        }
                    ],
                },
                'bad-row',
            ],
        }
        nested = {'metric': 'cogs', 'cogs': payload, 'period': 'month'}
        self.assertIsNotNone(extract_cogs_payload(nested))
        self.assertIsNotNone(extract_cogs_payload(payload))
        self.assertIsNone(extract_cogs_payload({'metric': 'expenses'}))

        xlsx = render_cogs_xlsx(payload)
        wb = load_workbook(BytesIO(xlsx))
        self.assertIn('Goods Sold', wb.sheetnames)
        self.assertEqual(wb['Goods Sold']['A1'].value, 'Sale number')

        csv_bytes = render_cogs_csv(payload)
        self.assertIn(b'Goods sold', csv_bytes)
        self.assertIn(b'Export Item', csv_bytes)

    def test_sales_workbook_goods_first(self):
        self._sale()
        goods = goods_sold_for_sales(posted_sales())
        payload = {
            'summary': {'total_sales': 1, 'total_revenue': 200.0, 'total_items': 2},
            'by_product': goods['by_product'],
            'sale_lines': goods['sale_lines'],
            'by_payment_method': [{'payment_method': 'cash', 'count': 1, 'total': 200.0}],
            'daily_breakdown': [{'day': '2026-11-04', 'count': 1, 'total': 200.0}],
            'sales': [
                {
                    'sale_number': 'S-EXP-1',
                    'date': timezone.now(),
                    'cashier': 'mgr',
                    'products': 'Export Item × 2',
                    'quantity': 2,
                    'total': 200.0,
                    'payment': 'cash',
                    'status': 'completed',
                }
            ],
        }
        self.assertTrue(is_sales_export_payload(payload))
        self.assertFalse(is_sales_export_payload({'summary': {}}))
        wb = load_workbook(BytesIO(render_sales_xlsx(payload)))
        self.assertEqual(wb.sheetnames[0], 'Goods Sold')
        self.assertIn('Sales', wb.sheetnames)
        self.assertIn(b'Quantity sold', render_sales_csv(payload))

    def test_maybe_export_helpers_respect_format(self):
        from django.test import RequestFactory

        factory = RequestFactory()
        cogs = {
            'cogs_sold': 1,
            'cogs_refunded': 0,
            'cogs': 1,
            'sales': [],
            'refunds': [],
            'sale_count': 0,
            'sales_shown': 0,
        }
        req = factory.get('/x', {'format': 'xlsx'})
        req.query_params = req.GET
        resp = maybe_export_cogs_workbook(req, cogs)
        self.assertIsNotNone(resp)
        self.assertEqual(resp['X-Report-Export'], 'xlsx')

        bare = factory.get('/x')
        bare.query_params = bare.GET
        self.assertIsNone(maybe_export_cogs_workbook(bare, cogs))

        pdf_req = factory.get('/x', {'format': 'pdf'})
        pdf_req.query_params = pdf_req.GET
        self.assertIsNone(maybe_export_cogs_workbook(pdf_req, cogs))

        bad = factory.get('/x', {'format': 'ppt'})
        bad.query_params = bad.GET
        bad_resp = maybe_export_cogs_workbook(bad, cogs)
        self.assertEqual(bad_resp.status_code, 400)

        truncated = dict(cogs)
        truncated['truncated'] = True
        truncated['sale_count'] = 9
        trunc_req = factory.get('/x', {'format': 'csv'})
        trunc_req.query_params = trunc_req.GET
        trunc_resp = maybe_export_cogs_workbook(trunc_req, truncated)
        self.assertEqual(trunc_resp['X-Export-Truncated'], '1')

        sales_payload = {
            'by_payment_method': [{'method': 'cash', 'count': 1, 'total': 1}],
            'by_product': [],
            'trend': [{'date': '2026-11-04', 'sales_count': 1, 'revenue': 1}],
            'lines_truncated': True,
            'line_count': 99,
        }
        req2 = factory.get('/y', {'format': 'csv'})
        req2.query_params = req2.GET
        self.assertIsNotNone(maybe_export_sales_workbook(req2, sales_payload))
        xlsx_req = factory.get('/y', {'format': 'xlsx'})
        xlsx_req.query_params = xlsx_req.GET
        sales_xlsx = maybe_export_sales_workbook(xlsx_req, sales_payload)
        self.assertEqual(sales_xlsx['X-Export-Truncated'], '1')
        self.assertIsNone(maybe_export_sales_workbook(None, sales_payload))
        self.assertIsNone(maybe_export_cogs_workbook(None, cogs))

    def test_trading_profit_feature_gate(self):
        SettingsService.set('reports', 'enable_financial_reports', True)
        module, _ = ModuleSettings.objects.get_or_create(
            module_name='reports',
            defaults={'is_enabled': True},
        )
        module.is_enabled = True
        module.save(update_fields=['is_enabled'])
        feat, _ = ModuleFeature.objects.get_or_create(
            module=module,
            feature_key='trading_profit',
            defaults={'feature_name': 'Trading profit', 'is_enabled': True},
        )
        feat.is_enabled = True
        feat.save(update_fields=['is_enabled'])
        self.assertTrue(reports_trading_profit_enabled())
        self.assertTrue(reports_action_enabled('trading_profit'))

        feat.is_enabled = False
        feat.save(update_fields=['is_enabled'])
        self.assertFalse(reports_trading_profit_enabled())
        self.assertFalse(reports_action_enabled('trading_profit'))

        feat.is_enabled = True
        feat.save(update_fields=['is_enabled'])
        SettingsService.set('reports', 'enable_financial_reports', False)
        self.assertFalse(reports_trading_profit_enabled())
        SettingsService.set('reports', 'enable_financial_reports', True)

    def test_cogs_export_edge_rows_and_import_error(self):
        import sys
        from unittest.mock import patch

        from reports import cogs_export

        self.assertEqual(cogs_export._d(None), Decimal('0'))
        self.assertEqual(cogs_export._d(''), Decimal('0'))
        self.assertEqual(cogs_export._d(Decimal('3')), Decimal('3'))
        self.assertEqual(cogs_export._d('not-a-number'), Decimal('0'))
        self.assertIsNone(cogs_export._num(None))
        self.assertIsNone(extract_cogs_payload('x'))
        nested = {
            'cogs': {'sales': [], 'cogs_sold': 0},
            'explanation': 'from parent',
            'period': 'week',
        }
        pulled = extract_cogs_payload(nested)
        self.assertEqual(pulled.get('explanation'), 'from parent')
        self.assertEqual(pulled.get('period'), 'week')

        sparse = {
            'cogs_sold': 0,
            'cogs_refunded': 0,
            'cogs': 0,
            'sales': [
                'skip',
                {'sale_number': 'S1', 'lines': ['bad', {'product_name': 'A', 'cost_missing': True}]},
            ],
            'refunds': [],
            'truncated': True,
            'sale_count': 5,
        }
        goods = cogs_export._goods_sold_rows(sparse)
        self.assertEqual(len(goods), 1)
        self.assertTrue(render_cogs_xlsx(sparse))
        self.assertTrue(render_cogs_csv(sparse))

        blocked = {
            k: None
            for k in list(sys.modules)
            if k == 'openpyxl' or k.startswith('openpyxl.')
        }
        blocked['openpyxl'] = None
        with patch.dict(sys.modules, blocked):
            with self.assertRaises(RuntimeError):
                render_cogs_xlsx(
                    {'sales': [], 'cogs_sold': 0, 'cogs_refunded': 0, 'cogs': 0}
                )

        from django.test import RequestFactory

        factory = RequestFactory()
        trunc = dict(sparse)
        req = factory.get('/x', {'format': 'xlsx'})
        req.query_params = req.GET
        resp = maybe_export_cogs_workbook(req, trunc)
        self.assertEqual(resp['X-Export-Truncated'], '1')
        self.assertIsNone(
            maybe_export_cogs_workbook(req, {'metric': 'expenses', 'total': 1})
        )

    def test_sales_export_skips_bad_row_shapes(self):
        payload = {
            'by_payment_method': ['x', {'payment_method': 'cash', 'count': 1, 'total': 2}],
            'by_product': ['x', {'product': 'P', 'quantity_sold': 1}],
            'sale_lines': [
                'x',
                {'sale_number': 'S1', 'sale_date': '2026-11-04T09:00:00', 'product': 'P'},
            ],
            'daily_breakdown': ['x', {'day': '2026-11-04', 'count': 1, 'total': 2}],
            'sales': [
                'x',
                {
                    'sale_number': 'S1',
                    'date': '2026-11-04T09:00:00',
                    'cashier': 'a',
                    'products': 'P',
                    'quantity': 1,
                    'total': 2,
                    'payment': 'cash',
                    'status': 'completed',
                },
            ],
            'lines_truncated': True,
            'line_count': 3,
        }
        self.assertFalse(is_sales_export_payload(None))
        self.assertTrue(render_sales_xlsx(payload))
        self.assertIn(b'P', render_sales_csv(payload))
        from django.test import RequestFactory

        factory = RequestFactory()
        req = factory.get('/y', {'format': 'xlsx'})
        req.query_params = req.GET
        resp = maybe_export_sales_workbook(req, payload)
        self.assertEqual(resp['X-Export-Truncated'], '1')

    def test_history_export_feature_blocks_api(self):
        self._sale()
        admin = self._admin_client()
        module, _ = ModuleSettings.objects.get_or_create(
            module_name='sales',
            defaults={'is_enabled': True},
        )
        feat, _ = ModuleFeature.objects.get_or_create(
            module=module,
            feature_key='history_export',
            defaults={'feature_name': 'Sales history export', 'is_enabled': True},
        )
        feat.is_enabled = False
        feat.save(update_fields=['is_enabled'])
        resp = admin.get('/api/sales/export/', {'format': 'xlsx'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, resp.data)

        feat.is_enabled = True
        feat.save(update_fields=['is_enabled'])
        ok = admin.get('/api/sales/export/', {'format': 'xlsx'})
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
