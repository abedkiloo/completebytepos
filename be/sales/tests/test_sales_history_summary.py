"""Sales history on-click period totals."""

from decimal import Decimal
from datetime import timedelta

from django.utils import timezone
from rest_framework import status

from products.models import Category, Product
from sales.models import Sale, SaleItem
from sales.sales_history_summary import summarize_sales_history
from utils.tests.api_test_base import ManagerAPITestCase


class SalesHistorySummaryTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        category = Category.objects.create(name='HistSum', is_active=True)
        self.product = Product.objects.create(
            name='Hist Item',
            sku='HIST-SUM-1',
            category=category,
            price=Decimal('100'),
            stock_quantity=50,
            track_stock=True,
            is_active=True,
        )
        now = timezone.now()
        self.day = timezone.localdate().isoformat()
        self.cash_sale = Sale.objects.create(
            sale_number='SALE-HIST-CASH',
            status='completed',
            sale_type='pos',
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
            amount_paid=Decimal('100.00'),
            payment_method='cash',
            cashier=self.manager_user,
            occurred_at=now,
        )
        SaleItem.objects.create(
            sale=self.cash_sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100'),
            subtotal=Decimal('100'),
        )
        self.mpesa_sale = Sale.objects.create(
            sale_number='SALE-HIST-MPESA',
            status='completed',
            sale_type='pos',
            subtotal=Decimal('250.00'),
            total=Decimal('250.00'),
            amount_paid=Decimal('250.00'),
            payment_method='mpesa',
            cashier=self.manager_user,
            occurred_at=now - timedelta(hours=1),
        )
        SaleItem.objects.create(
            sale=self.mpesa_sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('250'),
            subtotal=Decimal('250'),
        )

    def test_summarize_requires_date_range(self):
        with self.assertRaises(ValueError):
            summarize_sales_history(filters={'status': 'completed'}, request=None)

    def test_summarize_totals_by_method(self):
        payload = summarize_sales_history(
            filters={
                'date_from': self.day,
                'date_to': self.day,
                'status': 'completed',
            },
            request=None,
        )
        self.assertEqual(payload['count'], 2)
        self.assertEqual(Decimal(payload['total_amount']), Decimal('350.00'))
        methods = {row['payment_method']: row for row in payload['by_method']}
        self.assertEqual(methods['cash']['count'], 1)
        self.assertEqual(Decimal(methods['cash']['total']), Decimal('100.00'))
        self.assertEqual(methods['mpesa']['count'], 1)
        self.assertEqual(Decimal(methods['mpesa']['total']), Decimal('250.00'))

    def test_history_summary_endpoint(self):
        url = '/api/sales/history-summary/'
        res = self.client.get(
            url,
            {
                'date_from': self.day,
                'date_to': self.day,
                'status': 'completed',
            },
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 2)
        self.assertEqual(Decimal(res.data['total_amount']), Decimal('350.00'))

    def test_history_summary_rejects_missing_dates(self):
        res = self.client.get('/api/sales/history-summary/', {'status': 'completed'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
