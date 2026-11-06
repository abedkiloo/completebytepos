"""Overwrite sale-line unit_cost stamps with current catalog cost."""

from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from products.models import Category, Color, Product, ProductVariant, Size
from sales.models import Sale, SaleItem
from sales.rectify_sale_costs_to_catalog import (
    plan_catalog_cost_rectify,
    rectify_sale_costs_to_catalog,
)


class RectifySaleCostsToCatalogTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='rectify_cost', password='x')
        self.category = Category.objects.create(name='Rectify Cat', is_active=True)
        self.product = Product.objects.create(
            name='14* cookers [sofa pins]',
            sku='COOK-14',
            category=self.category,
            price=Decimal('300'),
            cost=Decimal('210'),
            stock_quantity=100,
            track_stock=True,
            is_active=True,
            has_variants=True,
        )
        self.size = Size.objects.create(name='14')
        self.color = Color.objects.create(name='GOLD')
        self.variant = ProductVariant.objects.create(
            product=self.product,
            size=self.size,
            color=self.color,
            sku='COOK-14-GOL',
            price=Decimal('300'),
            cost=Decimal('210.00'),
            stock_quantity=50,
            is_active=True,
        )
        self.sale = Sale.objects.create(
            sale_number='SALE-RECTIFY-1',
            status='completed',
            sale_type='pos',
            subtotal=Decimal('4300'),
            total=Decimal('4300'),
            amount_paid=Decimal('4300'),
            payment_method='cash',
            cashier=self.user,
            occurred_at=timezone.now(),
        )
        self.item = SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            variant=self.variant,
            quantity=10,
            unit_price=Decimal('430'),
            subtotal=Decimal('4300'),
            unit_cost=Decimal('248.33'),  # stale FIFO stamp
        )

    def test_plan_overwrites_stale_stamp_with_catalog(self):
        planned = plan_catalog_cost_rectify([self.item])
        self.assertEqual(len(planned), 1)
        self.assertEqual(planned[0].old_unit_cost, Decimal('248.33'))
        self.assertEqual(planned[0].new_unit_cost, Decimal('210.00'))
        self.assertIn('GOLD', planned[0].variant_label)

    def test_dry_run_does_not_write(self):
        planned, applied = rectify_sale_costs_to_catalog(
            sale_numbers=[self.sale.sale_number],
            apply=False,
        )
        self.assertEqual(len(planned), 1)
        self.assertEqual(applied, 0)
        self.item.refresh_from_db()
        self.assertEqual(self.item.unit_cost, Decimal('248.33'))

    def test_apply_writes_catalog_cost_and_is_idempotent(self):
        planned, applied = rectify_sale_costs_to_catalog(
            sale_numbers=[self.sale.sale_number],
            apply=True,
        )
        self.assertEqual(len(planned), 1)
        self.assertEqual(applied, 1)
        self.item.refresh_from_db()
        self.assertEqual(self.item.unit_cost, Decimal('210.00'))

        again, applied_again = rectify_sale_costs_to_catalog(
            sale_numbers=[self.sale.sale_number],
            apply=True,
        )
        self.assertEqual(again, [])
        self.assertEqual(applied_again, 0)

    def test_skips_when_catalog_cost_is_zero(self):
        self.variant.cost = Decimal('0')
        self.variant.save(update_fields=['cost'])
        self.product.cost = Decimal('0')
        self.product.save(update_fields=['cost'])
        planned, applied = rectify_sale_costs_to_catalog(
            sale_numbers=[self.sale.sale_number],
            apply=True,
        )
        self.assertEqual(planned, [])
        self.assertEqual(applied, 0)
        self.item.refresh_from_db()
        self.assertEqual(self.item.unit_cost, Decimal('248.33'))

    def test_management_command_apply(self):
        out = StringIO()
        call_command(
            'rectify_sale_costs_to_catalog',
            '--sale',
            self.sale.sale_number,
            '--apply',
            stdout=out,
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.unit_cost, Decimal('210.00'))
        self.assertIn('Updated 1', out.getvalue())
