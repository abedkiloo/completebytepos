"""API integration: product stock history admin gate + trail payload."""

from decimal import Decimal

from rest_framework import status

from products.models import Category, Product
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase
from utils.tests.module_setting_helpers import enable_inventory_api_features, enable_products_list_api_fields
from settings.test_utils import disable_maker_checker
from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from django.core.cache import cache


class ProductHistoryAdminAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Hist Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Hist Widget',
            sku='HIST-API-001',
            category=cat,
            price=Decimal('100'),
            cost=Decimal('50'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        disable_maker_checker()
        enable_products_list_api_fields()
        enable_inventory_api_features()

    def test_product_history_includes_stock_flow_trail(self):
        self.client.post(
            '/api/inventory/purchase/',
            {'product_id': self.product.id, 'quantity': 10, 'unit_cost': '50.00'},
            format='json',
        )
        response = self.client.get(
            '/api/inventory/product_history/',
            {'product_id': self.product.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertGreaterEqual(len(response.data), 1)
        row = response.data[0]
        self.assertIn('stock_flow', row)
        self.assertIn('previous_stock', row)
        self.assertIn('new_stock', row)
        self.assertIn('Previous stock', row['stock_flow'])
        self.assertIn('New stock', row['stock_flow'])

    def test_product_history_disabled_by_config(self):
        cache.clear()
        ModuleSetting.objects.update_or_create(
            module='inventory',
            key='show_product_stock_history',
            defaults={
                'label': 'Show product stock history',
                'default_value': False,
                'value': False,
            },
        )
        SettingsService.set('inventory', 'show_product_stock_history', False)
        response = self.client.get(
            '/api/inventory/product_history/',
            {'product_id': self.product.id},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_variant_product_requires_variant_id_and_filters(self):
        from products.models import ProductVariant

        self.product.has_variants = True
        self.product.stock_quantity = 0
        self.product.save(update_fields=['has_variants', 'stock_quantity'])
        variant_a = ProductVariant.objects.create(
            product=self.product,
            sku='HIST-API-001-A',
            price=Decimal('100'),
            cost=Decimal('50'),
            stock_quantity=10,
            is_active=True,
        )
        variant_b = ProductVariant.objects.create(
            product=self.product,
            sku='HIST-API-001-B',
            price=Decimal('100'),
            cost=Decimal('50'),
            stock_quantity=5,
            is_active=True,
        )
        self.client.post(
            '/api/inventory/purchase/',
            {
                'product_id': self.product.id,
                'variant_id': variant_a.id,
                'quantity': 3,
                'unit_cost': '50.00',
            },
            format='json',
        )
        self.client.post(
            '/api/inventory/purchase/',
            {
                'product_id': self.product.id,
                'variant_id': variant_b.id,
                'quantity': 2,
                'unit_cost': '50.00',
            },
            format='json',
        )

        missing = self.client.get(
            '/api/inventory/product_history/',
            {'product_id': self.product.id},
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST, missing.data)
        self.assertTrue(missing.data.get('requires_variant'))

        filtered = self.client.get(
            '/api/inventory/product_history/',
            {'product_id': self.product.id, 'variant_id': variant_a.id},
        )
        self.assertEqual(filtered.status_code, status.HTTP_200_OK, filtered.data)
        self.assertGreaterEqual(len(filtered.data), 1)
        for row in filtered.data:
            self.assertEqual(row.get('variant') or row.get('variant_id'), variant_a.id)


class ProductHistorySalesDeniedTests(SalesAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Sales Hist Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Sales Hist Widget',
            sku='HIST-SALES-001',
            category=cat,
            price=Decimal('20'),
            cost=Decimal('10'),
            stock_quantity=5,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        enable_inventory_api_features()

    def test_cashier_cannot_read_product_history(self):
        response = self.client.get(
            '/api/inventory/product_history/',
            {'product_id': self.product.id},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
