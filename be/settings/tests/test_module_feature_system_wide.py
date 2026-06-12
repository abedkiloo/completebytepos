"""
Module feature flags must match DB, API cache, and product behaviour system-wide.
"""

from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from products.models import Category, Color, Product, ProductVariant, Size
from products.serializers import ProductListSerializer
from settings.feature_flags import is_product_variants_enabled
from settings.module_catalog import build_modules_response, get_enabled_modules_flat
from settings.module_features import (
    FEATURE_DEFAULTS,
    is_module_feature_enabled,
    registry_default,
)
from settings.models import ModuleFeature, ModuleSettings
from settings.test_utils import disable_product_variants, enable_product_variants
from utils.tests.api_test_base import SuperAdminAPITestCase
from utils.tests.module_setting_helpers import enable_products_list_api_fields


class ModuleFeatureRegistryTests(TestCase):
    def test_product_variants_registry_default_is_off(self):
        self.assertFalse(registry_default('products', 'product_variants'))
        self.assertFalse(FEATURE_DEFAULTS['products']['product_variants'])


class ModuleFeatureResolverTests(TestCase):
    def setUp(self):
        call_command('init_modules', verbosity=0)

    def test_resolver_matches_db_row_when_present(self):
        enable_product_variants()
        self.assertTrue(is_module_feature_enabled('products', 'product_variants'))
        self.assertTrue(is_product_variants_enabled())

        disable_product_variants()
        self.assertFalse(is_module_feature_enabled('products', 'product_variants'))
        self.assertFalse(is_product_variants_enabled())

    def test_init_modules_does_not_reset_user_enabled_flag(self):
        enable_product_variants()
        call_command('init_modules', verbosity=0)
        feature = ModuleFeature.objects.get(
            module__module_name='products', feature_key='product_variants'
        )
        self.assertTrue(feature.is_enabled)
        self.assertTrue(is_product_variants_enabled())


class ModuleFeatureAPIConsistencyTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        call_command('init_modules', verbosity=0)

    def test_modules_api_exposes_registry_defaults(self):
        response = self.client.get('/api/settings/modules/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('registry', response.data)
        self.assertEqual(
            response.data['registry']['feature_defaults']['products']['product_variants'],
            False,
        )

    def test_flat_login_payload_matches_resolver(self):
        enable_product_variants()
        flat = get_enabled_modules_flat()
        self.assertIn('registry', flat)
        row = flat['products']['features']['product_variants']
        self.assertTrue(row['is_enabled'])
        self.assertTrue(is_module_feature_enabled('products', 'product_variants'))

        disable_product_variants()
        flat = get_enabled_modules_flat()
        row = flat['products']['features']['product_variants']
        self.assertFalse(row['is_enabled'])
        self.assertFalse(is_module_feature_enabled('products', 'product_variants'))

    def test_me_endpoint_enabled_modules_aligns_with_resolver(self):
        enable_product_variants()
        response = self.client.get('/api/accounts/auth/me/')
        self.assertEqual(response.status_code, 200)
        modules = response.data.get('enabled_modules', {})
        feature = modules['products']['features']['product_variants']
        self.assertEqual(feature['is_enabled'], is_product_variants_enabled())


class ProductVariantsCatalogModeTests(TestCase):
    """List/detail behaviour follows the same module flag as Module Settings UI."""

    def setUp(self):
        enable_products_list_api_fields()
        self.category = Category.objects.create(name='General', is_active=True)
        self.product = Product.objects.create(
            name='Variant',
            sku='VAR-FLAG-1',
            category=self.category,
            mrp=Decimal('500'),
            price=Decimal('500'),
            stock_quantity=400,
            track_stock=True,
            has_variants=True,
            is_active=True,
        )
        size = Size.objects.create(name='Default', code='DEF', is_active=True)
        color = Color.objects.create(name='Default', is_active=True)
        ProductVariant.objects.create(
            product=self.product,
            size=size,
            color=color,
            sku='VAR-FLAG-1-DEF',
            stock_quantity=400,
            is_active=True,
        )
        from products.stock_utils import sync_product_stock_from_variants

        sync_product_stock_from_variants(self.product)
        self.product.refresh_from_db()

    def test_list_hides_variants_when_feature_off_but_keeps_sellable_stock(self):
        disable_product_variants()
        data = ProductListSerializer(self.product).data
        self.assertFalse(data['has_variants'])
        self.assertEqual(int(data['stock_quantity']), 400)

    def test_list_shows_variants_when_feature_on(self):
        enable_product_variants()
        data = ProductListSerializer(self.product).data
        self.assertTrue(data['has_variants'])
