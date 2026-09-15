"""Report date filters use occurred_at and inclusive calendar-day bounds."""

from datetime import datetime, time
from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from products.models import Category, Product
from sales.models import Sale
from utils.tests.api_test_base import ManagerAPITestCase


class ReportDateFilterTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Date Filter Cat')
        cls.product = Product.objects.create(
            name='Date Filter Product',
            sku='RPT-DATE-001',
            category=cat,
            price=Decimal('10.00'),
            cost=Decimal('5.00'),
            stock_quantity=10,
            is_active=True,
        )

    def test_sales_report_same_calendar_day_includes_afternoon_sale(self):
        today = timezone.localdate()
        afternoon = timezone.make_aware(datetime.combine(today, time(15, 30)))
        Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('10.00'),
            total=Decimal('10.00'),
            amount_paid=Decimal('10.00'),
            cashier=self.manager_user,
            occurred_at=afternoon,
        )
        day = today.isoformat()
        response = self.client.get(
            '/api/reports/sales/',
            {'date_from': day, 'date_to': day},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['summary']['total_sales'], 1)
