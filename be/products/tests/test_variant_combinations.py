"""Explicit variant combination sync (not full size × color matrix)."""

from decimal import Decimal

from django.test import TestCase

from products.models import Category, Color, Product, ProductVariant, Size
from products.variant_combinations import (
    normalize_variant_combinations,
    sync_product_variant_combinations,
)
from settings.test_utils import disable_maker_checker


class VariantCombinationsTests(TestCase):
    def setUp(self):
        disable_maker_checker()
        self.category = Category.objects.create(name='Apparel', is_active=True)
        self.size_l = Size.objects.create(name='Large', code='L', is_active=True)
        self.size_m = Size.objects.create(name='Medium', code='M', is_active=True)
        self.color_white = Color.objects.create(name='White', is_active=True)
        self.color_blue = Color.objects.create(name='Blue', is_active=True)
        self.product = Product.objects.create(
            name='Shirt',
            sku='SHIRT-X',
            category=self.category,
            price=Decimal('100'),
            cost=Decimal('40'),
            has_variants=True,
            track_stock=True,
            is_active=True,
        )

    def test_normalize_variant_combinations_parses_json_pairs(self):
        raw = [
            {'size': self.size_l.id, 'color': self.color_white.id},
            {'size': self.size_m.id, 'color': self.color_blue.id},
        ]
        out = normalize_variant_combinations(raw)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]['size'], self.size_l.id)

    def test_sync_creates_only_explicit_pairs(self):
        sync_product_variant_combinations(
            self.product,
            [
                {'size': self.size_l.id, 'color': self.color_white.id},
                {'size': self.size_m.id, 'color': self.color_blue.id},
            ],
        )
        keys = set(
            ProductVariant.objects.filter(product=self.product).values_list(
                'size_id', 'color_id'
            )
        )
        self.assertEqual(
            keys,
            {
                (self.size_l.id, self.color_white.id),
                (self.size_m.id, self.color_blue.id),
            },
        )
        self.assertFalse(
            ProductVariant.objects.filter(
                product=self.product,
                size_id=self.size_l.id,
                color_id=self.color_blue.id,
            ).exists()
        )

    def test_sync_removes_variants_not_in_payload(self):
        sync_product_variant_combinations(
            self.product,
            [{'size': self.size_l.id, 'color': self.color_white.id}],
        )
        sync_product_variant_combinations(
            self.product,
            [{'size': self.size_m.id, 'color': self.color_blue.id}],
        )
        self.assertEqual(ProductVariant.objects.filter(product=self.product).count(), 1)
        variant = ProductVariant.objects.get(product=self.product)
        self.assertEqual(variant.size_id, self.size_m.id)
        self.assertEqual(variant.color_id, self.color_blue.id)
