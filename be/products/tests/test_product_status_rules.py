"""Tests for product status visibility rules (products_show_status store setting)."""

from django.test import TestCase

from products.models import Category, Product
from products.status_rules import (
    apply_operational_product_filter,
    get_operational_product,
    products_show_status_enabled,
    strip_product_status_filter,
    strip_product_status_from_write_data,
)
from django.core.cache import cache

from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class ProductStatusRulesUnitTests(TestCase):
    def setUp(self):
        cache.clear()
        ModuleSetting.objects.update_or_create(
            module='products',
            key='show_status',
            defaults={
                'label': 'Show product status',
                'description': '',
                'default_value': True,
                'value': True,
            },
        )
        self.category = Category.objects.create(name='Status Cat', is_active=True)
        self.active = Product.objects.create(
            name='Active Item',
            sku='ACT-001',
            category=self.category,
            price='100.00',
            cost='50.00',
            is_active=True,
        )
        self.inactive = Product.objects.create(
            name='Inactive Item',
            sku='INA-001',
            category=self.category,
            price='80.00',
            cost='40.00',
            is_active=False,
        )

    def test_products_show_status_enabled_defaults_true(self):
        SettingsService.set('products', 'show_status', True)
        self.assertTrue(products_show_status_enabled())

    def test_operational_filter_excludes_inactive_when_status_on(self):
        SettingsService.set('products', 'show_status', True)
        ids = list(
            apply_operational_product_filter(Product.objects.all()).values_list('id', flat=True)
        )
        self.assertIn(self.active.id, ids)
        self.assertNotIn(self.inactive.id, ids)

    def test_operational_filter_includes_inactive_when_status_off(self):
        SettingsService.set('products', 'show_status', False)
        ids = list(
            apply_operational_product_filter(Product.objects.all()).values_list('id', flat=True)
        )
        self.assertIn(self.active.id, ids)
        self.assertIn(self.inactive.id, ids)

    def test_get_operational_product_finds_inactive_when_status_off(self):
        SettingsService.set('products', 'show_status', False)
        product = get_operational_product(self.inactive.id)
        self.assertEqual(product.id, self.inactive.id)

    def test_strip_product_status_filter_removes_is_active_when_off(self):
        SettingsService.set('products', 'show_status', False)
        cleaned = strip_product_status_filter({'is_active': 'false', 'category': '1'})
        self.assertNotIn('is_active', cleaned)
        self.assertEqual(cleaned['category'], '1')

    def test_strip_product_status_from_write_data_preserves_db_value(self):
        SettingsService.set('products', 'show_status', False)
        data = strip_product_status_from_write_data({'name': 'X', 'is_active': False})
        self.assertNotIn('is_active', data)


class ProductListStatusIntegrationTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        ModuleSetting.objects.update_or_create(
            module='products',
            key='show_status',
            defaults={
                'label': 'Show product status',
                'description': '',
                'default_value': True,
                'value': True,
            },
        )
        self.category = Category.objects.create(name='List Cat', is_active=True)
        self.inactive = Product.objects.create(
            name='Hidden Inactive',
            sku='HID-001',
            category=self.category,
            price='10.00',
            cost='5.00',
            is_active=False,
        )

    def test_product_list_is_active_filter_ignored_when_show_status_off(self):
        SettingsService.set('products', 'show_status', False)

        response = self.client.get('/api/products/?is_active=false')
        self.assertEqual(response.status_code, 200)
        ids = [p['id'] for p in response.data.get('results', response.data)]
        self.assertIn(self.inactive.id, ids)

    def test_product_list_is_active_filter_applied_when_show_status_on(self):
        SettingsService.set('products', 'show_status', True)

        response = self.client.get('/api/products/?is_active=true')
        self.assertEqual(response.status_code, 200)
        rows = response.data.get('results', response.data)
        for row in rows:
            self.assertTrue(row['is_active'])


class ProductSearchStatusIntegrationTests(SalesAPITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        ModuleSetting.objects.update_or_create(
            module='products',
            key='show_status',
            defaults={
                'label': 'Show product status',
                'description': '',
                'default_value': True,
                'value': True,
            },
        )
        self.category = Category.objects.create(name='Search Cat', is_active=True)
        self.inactive = Product.objects.create(
            name='Sellable Inactive',
            sku='SAL-INA',
            category=self.category,
            price='25.00',
            cost='10.00',
            stock_quantity=50,
            track_stock=True,
            is_active=False,
        )

    def test_product_search_includes_inactive_when_show_status_off(self):
        SettingsService.set('products', 'show_status', False)

        response = self.client.get('/api/products/search/', {'q': 'Sellable'})
        self.assertEqual(response.status_code, 200)
        ids = [p['id'] for p in response.data]
        self.assertIn(self.inactive.id, ids)

    def test_product_search_excludes_inactive_when_show_status_on(self):
        SettingsService.set('products', 'show_status', True)

        response = self.client.get('/api/products/search/', {'q': 'Sellable'})
        self.assertEqual(response.status_code, 200)
        ids = [p['id'] for p in response.data]
        self.assertNotIn(self.inactive.id, ids)
