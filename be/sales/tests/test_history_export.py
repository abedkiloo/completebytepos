"""PDF / Excel / CSV export of sales history."""

from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from unittest.mock import patch

from products.models import Category, Product
from sales.history_export import SALES_HISTORY_EXPORT_LIMIT, build_sales_history_report
from sales.models import Sale, SaleItem
from sales.services import SaleService
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class SalesHistoryExportTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Hist Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Hist Product',
            sku='HIST-001',
            category=cat,
            price=Decimal('80.00'),
            cost=Decimal('40.00'),
            stock_quantity=10,
            is_active=True,
        )
        cls.sale = Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('80.00'),
            total=Decimal('80.00'),
            amount_paid=Decimal('80.00'),
            cashier=cls.manager_user,
        )
        SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            quantity=2,
            unit_price=Decimal('40.00'),
            subtotal=Decimal('80.00'),
        )
        Sale.objects.create(
            status='holding',
            payment_method='cash',
            subtotal=Decimal('10.00'),
            total=Decimal('10.00'),
            amount_paid=Decimal('0'),
            cashier=cls.manager_user,
        )

    def test_build_sales_history_report_skips_holding_when_queryset_excludes_it(self):
        qs = SaleService().build_queryset({}, request=None)
        data = build_sales_history_report(qs)
        self.assertEqual(data['summary']['sales_count'], 1)
        self.assertEqual(data['summary']['items_sold'], 2)
        self.assertEqual(data['summary']['total_revenue'], 80.0)
        self.assertEqual(len(data['sales']), 1)
        self.assertEqual(data['sales'][0]['payment'], 'cash')
        self.assertEqual(data['sales'][0]['quantity'], 2)
        self.assertIn('Hist Product', data['sales'][0]['products'])
        self.assertNotIn('customer', data['sales'][0])
        self.assertTrue(data['by_product'])
        self.assertEqual(data['by_product'][0]['product'], 'Hist Product')
        self.assertEqual(data['by_product'][0]['quantity_sold'], 2.0)
        self.assertEqual(len(data['sale_lines']), 1)
        self.assertEqual(data['sale_lines'][0]['product'], 'Hist Product')

    def test_export_pdf(self):
        response = self.client.get('/api/sales/export/', {'format': 'pdf'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('sales-history', response['Content-Disposition'])

    def test_export_excel(self):
        from io import BytesIO

        from openpyxl import load_workbook

        response = self.client.get('/api/sales/export/', {'format': 'xlsx'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(
            'spreadsheetml',
            response['Content-Type'],
        )
        self.assertTrue(response.content[:2] == b'PK')
        wb = load_workbook(BytesIO(response.content))
        self.assertEqual(wb.sheetnames[0], 'Goods Sold')
        self.assertIn('Sale Lines', wb.sheetnames)
        goods_headers = [c.value for c in wb['Goods Sold'][1]]
        self.assertEqual(goods_headers[0], 'Goods sold (product)')
        self.assertEqual(goods_headers[3], 'Quantity sold')
        # No customer column on Sales tickets sheet
        if 'Sales' in wb.sheetnames:
            sales_headers = [c.value for c in wb['Sales'][1]]
            self.assertIn('Products', sales_headers)
            self.assertNotIn('Customer', sales_headers)

    def test_export_csv(self):
        response = self.client.get('/api/sales/export/', {'format': 'csv'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.content.decode('utf-8-sig')
        self.assertIn('Goods sold (product)', body)
        self.assertIn('Hist Product', body)
        self.assertIn('Quantity sold', body)
        self.assertNotIn('Walk-in', body)

    def test_export_requires_format(self):
        response = self.client.get('/api/sales/export/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_rejects_bad_format(self):
        response = self.client.get('/api/sales/export/', {'format': 'ppt'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_honours_payment_filter(self):
        Sale.objects.create(
            status='completed',
            payment_method='mpesa',
            subtotal=Decimal('20.00'),
            total=Decimal('20.00'),
            amount_paid=Decimal('20.00'),
            cashier=self.manager_user,
        )
        qs = SaleService().build_queryset({'payment_method': 'mpesa'}, request=None)
        data = build_sales_history_report(qs)
        self.assertEqual(data['summary']['sales_count'], 1)
        self.assertEqual(data['sales'][0]['payment'], 'mpesa')

    def test_walk_in_unknown_payment_and_truncation(self):
        Sale.objects.filter(pk=self.sale.pk).update(payment_method='', cashier=None)
        extra = Sale.objects.create(
            status='completed',
            payment_method='card',
            subtotal=Decimal('5.00'),
            total=Decimal('0'),
            amount_paid=Decimal('0'),
            cashier=None,
        )
        SaleItem.objects.create(
            sale=extra,
            product=self.product,
            quantity=0,
            unit_price=Decimal('5.00'),
            subtotal=Decimal('0'),
        )
        qs = Sale.objects.filter(status='completed')
        data = build_sales_history_report(qs, limit=1)
        self.assertEqual(data['summary']['sales_count'], 2)
        self.assertTrue(data['summary']['truncated'])
        self.assertEqual(data['summary']['rows_in_file'], 1)
        empty_qs = Sale.objects.none()
        empty = build_sales_history_report(empty_qs)
        self.assertEqual(empty['summary']['sales_count'], 0)
        self.assertEqual(empty['summary']['items_sold'], 0)
        self.assertEqual(empty['sales'], [])
        self.assertEqual(SALES_HISTORY_EXPORT_LIMIT, 10000)

    def test_build_queryset_same_day_date_to_includes_afternoon_sale(self):
        from datetime import datetime, time

        today = timezone.localdate()
        afternoon = timezone.make_aware(datetime.combine(today, time(15, 30)))
        Sale.objects.filter(pk=self.sale.pk).update(occurred_at=afternoon)
        day_str = today.isoformat()
        qs = SaleService().build_queryset(
            {'date_from': day_str, 'date_to': day_str},
            request=None,
        )
        self.assertEqual(qs.count(), 1)

    @patch('sales.history_export.SALES_HISTORY_EXPORT_LIMIT', 1)
    def test_export_sets_truncation_headers(self):
        Sale.objects.create(
            status='completed',
            payment_method='mpesa',
            subtotal=Decimal('20.00'),
            total=Decimal('20.00'),
            amount_paid=Decimal('20.00'),
            cashier=self.manager_user,
        )
        response = self.client.get('/api/sales/export/', {'format': 'csv'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('X-Export-Truncated'), '1')
        self.assertEqual(response.get('X-Export-Total-Count'), '2')

    def test_walk_in_row_labels(self):
        Sale.objects.filter(pk=self.sale.pk).update(payment_method='', cashier=None)
        self.sale.refresh_from_db()
        data = build_sales_history_report(Sale.objects.filter(pk=self.sale.pk))
        row = data['sales'][0]
        self.assertEqual(row['cashier'], '')
        self.assertNotIn('customer', row)
        self.assertIn('Hist Product', row['products'])
        self.assertEqual(row['payment'], '')
        self.assertEqual(data['by_payment_method'][0]['payment_method'], 'unknown')


class SalesHistoryExportPersonaTests(SalesAPITestCase):
    def test_sales_persona_can_export_history(self):
        response = self.client.get('/api/sales/export/', {'format': 'pdf'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.content.startswith(b'%PDF'))
