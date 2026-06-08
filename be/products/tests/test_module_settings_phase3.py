"""Phase 3 — products module settings gates."""

from django.core.cache import cache
from rest_framework import status

from products.models import Category, Product
from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase, SuperAdminAPITestCase


def _seed_products_settings():
    cache.clear()
    for key, default in (
        ('show_status', True),
        ('show_cost_price', True),
        ('show_mrp', True),
        ('show_sku_in_list', False),
        ('show_low_stock_badges', True),
        ('enable_bulk_operations', True),
        ('enable_csv_import_export', True),
        ('allow_sales_catalog_access', True),
        ('allow_sales_edit_catalog_details', True),
        ('allow_sales_edit_pricing', False),
        ('allow_sales_edit_cost', False),
        ('allow_sales_edit_stock', False),
        ('allow_manager_edit_pricing', True),
        ('allow_manager_edit_cost', False),
    ):
        ModuleSetting.objects.update_or_create(
            module='products',
            key=key,
            defaults={
                'label': key,
                'description': '',
                'default_value': default,
                'value': default,
            },
        )


class ProductSerializerFlagsUnitTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_products_settings()
        self.category = Category.objects.create(name='Flag Cat', is_active=True)
        self.product = Product.objects.create(
            name='Flag Product',
            sku='FLG-1',
            category=self.category,
            price='100.00',
            mrp='120.00',
            cost='40.00',
            is_active=True,
        )

    def test_list_omits_cost_when_show_cost_price_off(self):
        SettingsService.set('products', 'show_cost_price', False)
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = next(
            p for p in response.data.get('results', response.data) if p['id'] == self.product.id
        )
        self.assertNotIn('cost', row)

    def test_list_omits_mrp_when_show_mrp_off(self):
        SettingsService.set('products', 'show_mrp', False)
        response = self.client.get('/api/products/')
        row = next(
            p for p in response.data.get('results', response.data) if p['id'] == self.product.id
        )
        self.assertNotIn('mrp', row)

    def test_list_omits_sku_when_show_sku_in_list_off(self):
        SettingsService.set('products', 'show_sku_in_list', False)
        response = self.client.get('/api/products/')
        row = next(
            p for p in response.data.get('results', response.data) if p['id'] == self.product.id
        )
        self.assertNotIn('sku', row)


class ProductBulkCsvIntegrationTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_products_settings()
        self.category = Category.objects.create(name='Bulk Cat', is_active=True)
        self.product = Product.objects.create(
            name='Bulk Product',
            sku='BLK-1',
            category=self.category,
            price='10.00',
            cost='5.00',
            is_active=True,
        )

    def test_bulk_delete_forbidden_when_bulk_operations_off(self):
        SettingsService.set('products', 'enable_bulk_operations', False)
        response = self.client.post(
            '/api/products/bulk_delete/',
            {'product_ids': [self.product.id]},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_forbidden_when_csv_import_export_off(self):
        SettingsService.set('products', 'enable_csv_import_export', False)
        response = self.client.get('/api/products/export/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_allowed_when_csv_import_export_on(self):
        SettingsService.set('products', 'enable_csv_import_export', True)
        response = self.client.get('/api/products/export/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
