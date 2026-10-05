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

    def test_normalize_variant_combinations_parses_json_string(self):
        import json

        raw = json.dumps(
            [
                {'size': self.size_l.id, 'color': self.color_white.id},
            ]
        )
        out = normalize_variant_combinations(raw)
        self.assertEqual(len(out), 1)

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

    def test_similar_color_names_get_distinct_skus(self):
        """GOLD and GOLD/ BLACK both truncate to GOL — must not collide."""
        gold = Color.objects.create(name='GOLD', is_active=True)
        gold_black = Color.objects.create(name='GOLD/ BLACK', is_active=True)
        size = Size.objects.create(name='14', code='14', is_active=True)
        sync_product_variant_combinations(
            self.product,
            [
                {'size': size.id, 'color': gold.id},
                {'size': size.id, 'color': gold_black.id},
            ],
        )
        variants = list(ProductVariant.objects.filter(product=self.product))
        self.assertEqual(len(variants), 2)
        skus = {v.sku for v in variants}
        self.assertEqual(len(skus), 2)
        self.assertTrue(all(sku.startswith('SHIRT-X-14-GOL') for sku in skus))


class VariantProductCreateAPITests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        from settings.test_utils import disable_maker_checker, enable_product_variants

        disable_maker_checker()
        enable_product_variants()
        self.client = APIClient()
        self.user = User.objects.create_superuser('var_admin', 'v@t.com', 'x')
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.category = Category.objects.create(name='Cookers', is_active=True)
        self.size = Size.objects.create(name='14', code='14', is_active=True)
        self.colors = [
            Color.objects.create(name='Bronze', is_active=True),
            Color.objects.create(name='copper Bronze[brown]', is_active=True),
            Color.objects.create(name='GOLD', is_active=True),
            Color.objects.create(name='GOLD/ BLACK', is_active=True),
            Color.objects.create(name='SILVER', is_active=True),
        ]

    def test_create_with_many_similar_color_variants_succeeds(self):
        import json

        combinations = [
            {'size': self.size.id, 'color': c.id} for c in self.colors
        ]
        response = self.client.post(
            '/api/products/',
            {
                'name': '14* cookers [sofa pins]',
                'category': self.category.id,
                'price': '300',
                'cost': '210',
                'has_variants': True,
                'track_stock': True,
                'available_sizes': [self.size.id],
                'available_colors': [c.id for c in self.colors],
                'variant_combinations': json.dumps(combinations),
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 201, response.data)
        product = Product.objects.get(pk=response.data['id'])
        self.assertEqual(
            ProductVariant.objects.filter(product=product).count(),
            5,
        )
        skus = list(
            ProductVariant.objects.filter(product=product).values_list('sku', flat=True)
        )
        self.assertEqual(len(skus), len(set(skus)))

    def test_failed_variant_sync_does_not_leave_orphan_product(self):
        import json
        from unittest.mock import patch

        combinations = [{'size': self.size.id, 'color': self.colors[0].id}]
        with patch(
            'products.variant_combinations.sync_product_variant_combinations',
            side_effect=RuntimeError('boom'),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    '/api/products/',
                    {
                        'name': 'Should Roll Back',
                        'category': self.category.id,
                        'price': '100',
                        'cost': '40',
                        'has_variants': True,
                        'track_stock': True,
                        'available_sizes': [self.size.id],
                        'available_colors': [self.colors[0].id],
                        'variant_combinations': json.dumps(combinations),
                    },
                    format='multipart',
                )
        self.assertFalse(Product.objects.filter(name='Should Roll Back').exists())
