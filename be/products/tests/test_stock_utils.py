"""Tests for sellable stock aggregation (parent + variants)."""

from decimal import Decimal

from django.test import TestCase

from products.models import Category, Product, ProductVariant, Size, Color
from products.stock_utils import (
    active_variant_stock_sum,
    apply_catalog_variant_representation,
    sellable_stock_quantity,
    sellable_unit_cost,
    sellable_unit_price,
    sync_product_stock_from_variants,
    variants_sold_as_simple,
)
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

    def test_variant_product_with_no_rows_has_zero_sellable(self):
        self.assertEqual(sellable_stock_quantity(self.product, variant=None), 0)

    def test_sellable_stock_is_sum_of_variant_rows(self):
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

    def test_apply_catalog_variant_representation_sets_sellable_stock(self):
        size = Size.objects.create(name='S', code='S', is_active=True)
        color = Color.objects.create(name='Red', is_active=True)
        ProductVariant.objects.create(
            product=self.product,
            size=size,
            color=color,
            sku='SOFA-1-S-R',
            stock_quantity=435,
            is_active=True,
        )
        sync_product_stock_from_variants(self.product)
        data = apply_catalog_variant_representation(
            self.product,
            {'stock_quantity': 0, 'has_variants': True, 'price': '80'},
        )
        self.assertFalse(data['has_variants'])
        self.assertEqual(data['stock_quantity'], 435)

    def test_apply_catalog_sets_min_variant_price_when_parent_zero(self):
        size = Size.objects.create(name='S2', code='S2', is_active=True)
        color = Color.objects.create(name='Yellow', is_active=True)
        ProductVariant.objects.create(
            product=self.product,
            size=size,
            color=color,
            sku='SOFA-1-S-Y',
            price=Decimal('125'),
            stock_quantity=1,
            is_active=True,
        )
        data = apply_catalog_variant_representation(
            self.product,
            {'price': '0', 'selling_price': '0', 'has_variants': True},
        )
        self.assertEqual(data['price'], '125.00')
        self.assertEqual(data['selling_price'], data['price'])

    def test_variants_sold_as_simple_when_feature_off(self):
        self.assertTrue(variants_sold_as_simple(self.product))

    def test_apply_catalog_noop_without_variants(self):
        plain = Product.objects.create(
            name='Plain',
            sku='PLAIN-1',
            category=self.cat,
            price=Decimal('10'),
            stock_quantity=3,
            has_variants=False,
            is_active=True,
        )
        data = apply_catalog_variant_representation(plain, {'stock_quantity': 3})
        self.assertEqual(data['stock_quantity'], 3)

    def test_sellable_unit_price_and_cost(self):
        size = Size.objects.create(name='M', code='M', is_active=True)
        color = Color.objects.create(name='Blue', is_active=True)
        variant = ProductVariant.objects.create(
            product=self.product,
            size=size,
            color=color,
            sku='SOFA-1-M-B',
            price=Decimal('90'),
            cost=Decimal('40'),
            stock_quantity=2,
            is_active=True,
        )
        self.assertEqual(sellable_unit_price(self.product, variant=variant), Decimal('90'))
        self.assertEqual(sellable_unit_cost(self.product, variant=variant), Decimal('40'))
        self.assertEqual(
            sellable_unit_price(self.product, override=Decimal('77')),
            Decimal('77'),
        )
        self.product.price = Decimal('0')
        self.product.save(update_fields=['price'])
        self.assertEqual(sellable_unit_price(self.product), Decimal('90'))

    def test_sellable_unit_price_zero_when_no_prices(self):
        bare = Product.objects.create(
            name='Bare',
            sku='BARE-1',
            category=self.cat,
            price=Decimal('0'),
            stock_quantity=1,
            has_variants=False,
            is_active=True,
        )
        self.assertEqual(sellable_unit_price(bare), Decimal('0'))

    def test_variant_row_stock_quantity(self):
        size = Size.objects.create(name='L', code='L', is_active=True)
        color = Color.objects.create(name='Green', is_active=True)
        variant = ProductVariant.objects.create(
            product=self.product,
            size=size,
            color=color,
            sku='SOFA-1-L-G',
            stock_quantity=7,
            is_active=True,
        )
        self.assertEqual(sellable_stock_quantity(self.product, variant=variant), 7)

    def test_variant_zero_is_zero_even_when_parent_has_stale_stock(self):
        size = Size.objects.create(name='S', code='S', is_active=True)
        color = Color.objects.create(name='Red', is_active=True)
        variant = ProductVariant.objects.create(
            product=self.product,
            size=size,
            color=color,
            sku='SOFA-1-S-R',
            stock_quantity=0,
            is_active=True,
        )
        self.product.stock_quantity = 400
        self.product.save(update_fields=['stock_quantity'])
        self.assertEqual(active_variant_stock_sum(self.product), 0)
        self.assertEqual(sellable_stock_quantity(self.product, variant=variant), 0)

    def test_variant_zero_not_parent_when_other_variants_hold_stock(self):
        size_a = Size.objects.create(name='A', code='A', is_active=True)
        size_b = Size.objects.create(name='B', code='B', is_active=True)
        color = Color.objects.create(name='Red', is_active=True)
        ProductVariant.objects.create(
            product=self.product,
            size=size_a,
            color=color,
            sku='SOFA-A',
            stock_quantity=10,
            is_active=True,
        )
        variant_b = ProductVariant.objects.create(
            product=self.product,
            size=size_b,
            color=color,
            sku='SOFA-B',
            stock_quantity=0,
            is_active=True,
        )
        self.product.stock_quantity = 5
        self.product.save(update_fields=['stock_quantity'])
        self.assertEqual(sellable_stock_quantity(self.product, variant=variant_b), 0)


class SyncProductStockFromVariantsTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='Cat', is_active=True)
        self.product = Product.objects.create(
            name='Shirt',
            sku='SHIRT-1',
            category=self.cat,
            price=Decimal('50'),
            stock_quantity=999,
            track_stock=True,
            has_variants=True,
            is_active=True,
        )
        self.size = Size.objects.create(name='M', code='M', is_active=True)
        self.color_a = Color.objects.create(name='White', is_active=True)
        self.color_b = Color.objects.create(name='Blue', is_active=True)

    def test_sync_sets_parent_to_variant_sum(self):
        ProductVariant.objects.create(
            product=self.product,
            size=self.size,
            color=self.color_a,
            sku='SHIRT-W',
            stock_quantity=200,
            is_active=True,
        )
        ProductVariant.objects.create(
            product=self.product,
            size=self.size,
            color=self.color_b,
            sku='SHIRT-B',
            stock_quantity=40,
            is_active=True,
        )
        total = sync_product_stock_from_variants(self.product)
        self.assertEqual(total, 240)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 240)

    def test_sync_ignores_inactive_variants(self):
        ProductVariant.objects.create(
            product=self.product,
            size=self.size,
            color=self.color_a,
            sku='SHIRT-W',
            stock_quantity=10,
            is_active=True,
        )
        ProductVariant.objects.create(
            product=self.product,
            size=self.size,
            color=self.color_b,
            sku='SHIRT-B',
            stock_quantity=100,
            is_active=False,
        )
        sync_product_stock_from_variants(self.product)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
