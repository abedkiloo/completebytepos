"""Tests for sellable stock aggregation (parent + variants)."""

from decimal import Decimal

from django.test import TestCase

from products.models import Category, Product, ProductVariant, Size, Color
from products.stock_utils import sellable_stock_quantity
from settings.test_utils import disable_product_variants


class SellableStockQuantityTests(TestCase):
    def setUp(self):
        disable_product_variants()
        self.cat = Category.objects.create(name='Cat', is_active=True)
        self.product = Product.objects.create(
            name='Sofa',
            sku='SOFA-1',
            category=self.cat,
            mrp=Decimal('100'),
            price=Decimal('80'),
            stock_quantity=435,
            track_stock=True,
            has_variants=True,
            is_active=True,
        )

    def test_parent_stock_when_variant_rows_empty(self):
        """Checkout must see parent quantity when no variant stock rows exist."""
        self.assertEqual(sellable_stock_quantity(self.product, variant=None), 435)

    def test_max_of_parent_and_variant_sum(self):
        size = Size.objects.create(name='S', code='S', is_active=True)
        color = Color.objects.create(name='Red', is_active=True)
        ProductVariant.objects.create(
            product=self.product,
            size=size,
            color=color,
            sku='SOFA-1-S-R',
            stock_quantity=10,
            is_active=True,
        )
        self.product.stock_quantity = 5
        self.product.save()
        self.assertEqual(sellable_stock_quantity(self.product, variant=None), 10)
