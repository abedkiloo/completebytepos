"""Payments trail Show total is admin-only."""

from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from products.models import Category, Product
from sales.models import Customer, Sale, SaleItem
from utils.tests.api_test_base import SuperAdminAPITestCase


class PaymentsTrailSummaryAdminTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()
        self.customer = Customer.objects.create(
            name='Admin Total',
            phone='0700111222',
            is_active=True,
        )
        category = Category.objects.create(name='PTS', is_active=True)
        product = Product.objects.create(
            name='PTS Item',
            sku='PTS-1',
            category=category,
            price=Decimal('100'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )
        sale = Sale.objects.create(
            sale_number='SALE-PTS-1',
            status='completed',
            sale_type='pos',
            customer=self.customer,
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
            amount_paid=Decimal('100.00'),
            payment_method='cash',
            cashier=self.admin,
            occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=1,
            unit_price=Decimal('100'),
            subtotal=Decimal('100'),
        )

    def test_admin_can_calculate_payments_trail_total(self):
        response = self.client.get(
            '/api/sales/customers/payments-trail/summary/',
            {
                'date_from': self.today.isoformat(),
                'date_to': self.today.isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertGreaterEqual(response.data['count'], 1)
        self.assertGreater(Decimal(response.data['total_amount']), Decimal('0'))
