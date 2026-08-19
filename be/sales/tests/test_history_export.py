"""PDF / Excel / CSV export of sales history."""

from decimal import Decimal

from rest_framework import status

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
        self.assertEqual(data['sales'][0]['items'], 2)

    def test_export_pdf(self):
        response = self.client.get('/api/sales/export/', {'format': 'pdf'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('sales-history', response['Content-Disposition'])

    def test_export_excel(self):
        response = self.client.get('/api/sales/export/', {'format': 'xlsx'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(
            'spreadsheetml',
            response['Content-Type'],
        )
        self.assertTrue(response.content[:2] == b'PK')

    def test_export_csv(self):
        response = self.client.get('/api/sales/export/', {'format': 'csv'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.content.decode('utf-8-sig')
        self.assertIn('Sale Number', body)

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
        self.assertEqual(SALES_HISTORY_EXPORT_LIMIT, 2000)

    def test_walk_in_row_labels(self):
        Sale.objects.filter(pk=self.sale.pk).update(payment_method='', cashier=None)
        self.sale.refresh_from_db()
        data = build_sales_history_report(Sale.objects.filter(pk=self.sale.pk))
        row = data['sales'][0]
        self.assertEqual(row['cashier'], '')
        self.assertEqual(row['customer'], 'Walk-in')
        self.assertEqual(row['payment'], '')
        self.assertEqual(data['by_payment_method'][0]['payment_method'], 'unknown')


class SalesHistoryExportPersonaTests(SalesAPITestCase):
    def test_sales_persona_can_export_history(self):
        response = self.client.get('/api/sales/export/', {'format': 'pdf'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.content.startswith(b'%PDF'))
