"""Unapproved sales must not appear in books or reports."""

from decimal import Decimal

from django.test import TestCase

from reports.sale_scope import POSTED_SALE_STATUS, posted_sale_items, posted_sales
from reports.views import sale_report_queryset
from sales.models import Sale, SaleItem
from products.models import Category, Product


class PostedSaleScopeTests(TestCase):
    def setUp(self):
        cat = Category.objects.create(name='Scope Cat', is_active=True)
        self.product = Product.objects.create(
            name='Scope SKU',
            sku='SCOPE-1',
            category=cat,
            price=Decimal('10'),
            cost=Decimal('4'),
            stock_quantity=5,
            is_active=True,
        )
        self.completed = Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            amount_paid=Decimal('10'),
        )
        SaleItem.objects.create(
            sale=self.completed,
            product=self.product,
            quantity=1,
            unit_price=Decimal('10'),
            subtotal=Decimal('10'),
        )
        self.pending = Sale.objects.create(
            status='pending_approval',
            payment_method='cash',
            subtotal=Decimal('99'),
            total=Decimal('99'),
            amount_paid=Decimal('99'),
        )
        SaleItem.objects.create(
            sale=self.pending,
            product=self.product,
            quantity=1,
            unit_price=Decimal('99'),
            subtotal=Decimal('99'),
        )
        self.holding = Sale.objects.create(
            status='holding',
            payment_method='cash',
            subtotal=Decimal('50'),
            total=Decimal('50'),
            amount_paid=Decimal('0'),
        )
        self.cancelled = Sale.objects.create(
            status='cancelled',
            payment_method='cash',
            subtotal=Decimal('40'),
            total=Decimal('40'),
            amount_paid=Decimal('40'),
        )

    def test_posted_sales_are_completed_only(self):
        self.assertEqual(POSTED_SALE_STATUS, 'completed')
        ids = set(posted_sales().values_list('id', flat=True))
        self.assertEqual(ids, {self.completed.id})
        self.assertEqual(
            set(posted_sale_items().values_list('sale_id', flat=True)),
            {self.completed.id},
        )

    def test_report_queryset_ignores_unposted_sales(self):
        qs = sale_report_queryset()
        self.assertTrue(qs.filter(pk=self.completed.pk).exists())
        self.assertFalse(qs.filter(pk=self.pending.pk).exists())
        self.assertFalse(qs.filter(pk=self.holding.pk).exists())
        self.assertFalse(qs.filter(pk=self.cancelled.pk).exists())
