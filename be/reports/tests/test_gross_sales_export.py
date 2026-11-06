"""Gross sales breakdown Excel/CSV — totals must tie out to Trading profit."""

from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SUPER_ADMIN, ensure_permissions, sync_default_roles
from products.models import Category, Product
from reports.gross_sales_export import (
    is_gross_sales_export_payload,
    maybe_export_gross_sales_workbook,
    render_gross_sales_csv,
    sale_export_rows,
)
from sales.models import Sale, SaleItem
from utils.tests.api_test_base import ManagerAPITestCase


class GrossSalesExportTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ensure_permissions()
        sync_default_roles()
        cls.cat = Category.objects.create(name='GS Cat', is_active=True)
        cls.product = Product.objects.create(
            name='GS Item',
            sku='GS-1',
            category=cls.cat,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=50,
            track_stock=True,
            is_active=True,
        )

    def _admin_client(self):
        admin = User.objects.create_user('gs_admin', password='x', is_staff=True)
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

    def _seed_sales(self):
        now = timezone.now()
        cash = Sale.objects.create(
            sale_number='S-GS-CASH',
            status='completed',
            subtotal=Decimal('100'),
            total=Decimal('100'),
            amount_paid=Decimal('100'),
            payment_method='cash',
            cashier=self.manager_user,
            occurred_at=now,
        )
        SaleItem.objects.create(
            sale=cash,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100'),
            unit_cost=Decimal('40'),
            subtotal=Decimal('100'),
        )
        mpesa = Sale.objects.create(
            sale_number='S-GS-MPESA',
            status='completed',
            subtotal=Decimal('250'),
            total=Decimal('250'),
            amount_paid=Decimal('250'),
            payment_method='mpesa',
            cashier=self.manager_user,
            occurred_at=now,
        )
        SaleItem.objects.create(
            sale=mpesa,
            product=self.product,
            quantity=1,
            unit_price=Decimal('250'),
            unit_cost=Decimal('40'),
            subtotal=Decimal('250'),
        )
        return cash, mpesa

    def test_breakdown_rows_sum_equals_total_and_trading_profit(self):
        self._seed_sales()
        admin = self._admin_client()

        profit = admin.get('/api/reports/trading_profit/', {'period': 'month'})
        self.assertEqual(profit.status_code, status.HTTP_200_OK, profit.data)
        gross_from_profit = Decimal(str(profit.data['summary']['gross_sales']))
        self.assertEqual(gross_from_profit, Decimal('350.00'))

        breakdown = admin.get(
            '/api/reports/trading_profit/breakdown/',
            {'period': 'month', 'metric': 'gross_sales'},
        )
        self.assertEqual(breakdown.status_code, status.HTTP_200_OK, breakdown.data)
        self.assertEqual(breakdown.data['metric'], 'gross_sales')
        total = Decimal(str(breakdown.data['total']))
        self.assertEqual(total, gross_from_profit)

        rows_sum = sum(
            (Decimal(str(row['amount'])) for row in breakdown.data['rows']),
            Decimal('0'),
        )
        self.assertEqual(rows_sum, total)
        self.assertFalse(breakdown.data.get('truncated'))
        self.assertEqual(breakdown.data['row_count'], 2)

    def test_excel_and_csv_export_tally_with_total(self):
        self._seed_sales()
        admin = self._admin_client()
        params = {'period': 'month', 'metric': 'gross_sales'}

        xlsx = admin.get(
            '/api/reports/trading_profit/breakdown/',
            {**params, 'format': 'xlsx'},
        )
        self.assertEqual(xlsx.status_code, status.HTTP_200_OK)
        self.assertEqual(xlsx['X-Report-Export'], 'xlsx')
        self.assertIn(
            'spreadsheetml',
            xlsx['Content-Type'],
        )
        self.assertGreater(len(xlsx.content), 100)

        from openpyxl import load_workbook

        wb = load_workbook(BytesIO(xlsx.content), data_only=True)
        self.assertIn('Sales', wb.sheetnames)
        self.assertIn('Summary', wb.sheetnames)
        sales_ws = wb['Sales']
        # Header + 2 sales
        sale_totals = []
        for row in sales_ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            sale_totals.append(Decimal(str(row[4])))
        self.assertEqual(sum(sale_totals), Decimal('350.00'))

        summary_ws = wb['Summary']
        summary_map = {
            str(row[0]): row[1]
            for row in summary_ws.iter_rows(min_row=1, max_col=2, values_only=True)
            if row and row[0]
        }
        self.assertEqual(
            Decimal(str(summary_map['TOTAL (gross sales)'])),
            Decimal('350.00'),
        )
        self.assertEqual(
            Decimal(str(summary_map['Sum of sale totals (this workbook)'])),
            Decimal('350.00'),
        )
        self.assertEqual(
            Decimal(
                str(
                    summary_map[
                        'Tie-out: workbook sum − TOTAL (must be 0 if not truncated)'
                    ]
                )
            ),
            Decimal('0.00'),
        )

        csv_resp = admin.get(
            '/api/reports/trading_profit/breakdown/',
            {**params, 'format': 'csv'},
        )
        self.assertEqual(csv_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(csv_resp['X-Report-Export'], 'csv')
        text = csv_resp.content.decode('utf-8-sig')
        self.assertIn('S-GS-CASH', text)
        self.assertIn('S-GS-MPESA', text)
        self.assertIn('TOTAL', text)
        self.assertIn('350', text)

    def test_helpers_detect_payload_and_skip_non_export(self):
        payload = {
            'metric': 'gross_sales',
            'title': 'Gross sales',
            'total': 10,
            'rows': [
                {
                    'label': 'S-1',
                    'amount': 10,
                    'amount_paid': 10,
                    'unpaid': 0,
                    'occurred_at': '2026-11-06T10:00:00+03:00',
                    'payment_method': 'cash',
                    'lines': [
                        {
                            'product_name': 'Widget',
                            'quantity': 1,
                            'unit_price': 10,
                            'line_total': 10,
                        }
                    ],
                }
            ],
            'row_count': 1,
            'rows_shown': 1,
            'truncated': False,
        }
        self.assertTrue(is_gross_sales_export_payload(payload))
        self.assertFalse(is_gross_sales_export_payload({'metric': 'cogs', 'rows': []}))
        self.assertEqual(len(sale_export_rows(payload)), 1)
        self.assertIn(b'TOTAL', render_gross_sales_csv(payload))

        from django.test import RequestFactory

        factory = RequestFactory()
        bare = factory.get('/x')
        bare.query_params = bare.GET
        self.assertIsNone(maybe_export_gross_sales_workbook(bare, payload))
        self.assertIsNone(maybe_export_gross_sales_workbook(None, payload))
