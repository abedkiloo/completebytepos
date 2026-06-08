"""Phase 4 — cross-module feature-flag integration and data integrity."""

from decimal import Decimal

from django.core.cache import cache
from rest_framework import status

from products.models import Category, Product
from settings.models import ModuleSetting, StoreSettings
from settings.module_settings_registry import MODULE_SETTING_DEFINITIONS
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


class ModuleSettingsDataIntegrityTests(ManagerAPITestCase):
    """Disabled flags must not mutate stored data; re-enable restores behaviour."""

    def setUp(self):
        super().setUp()
        _seed_products_settings()
        cat = Category.objects.create(name='Phase4 Cat', is_active=True)
        self.inactive = Product.objects.create(
            name='Inactive SKU',
            sku='P4-INACTIVE',
            category=cat,
            price=Decimal('50.00'),
            stock_quantity=10,
            is_active=False,
            track_stock=True,
        )

    def test_inactive_product_still_listed_when_show_status_off(self):
        SettingsService.set('products', 'show_status', False)
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', response.data)
        ids = [row['id'] for row in rows]
        self.assertIn(self.inactive.id, ids)
        self.inactive.refresh_from_db()
        self.assertFalse(self.inactive.is_active)

    def test_reenable_show_status_restores_inactive_filter(self):
        SettingsService.set('products', 'show_status', True)
        response = self.client.get('/api/products/?is_active=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', response.data)
        self.assertTrue(any(row['id'] == self.inactive.id for row in rows))

    def test_toggle_show_status_does_not_change_stored_is_active(self):
        SettingsService.set('products', 'show_status', False)
        self.client.get('/api/products/products/')
        SettingsService.set('products', 'show_status', True)
        self.inactive.refresh_from_db()
        self.assertFalse(self.inactive.is_active)


class ModuleSettingsRegistryIntegrationTests(SuperAdminAPITestCase):
    """Every Phase 3 module is reachable via the settings API."""

    def setUp(self):
        super().setUp()
        cache.clear()
        for module, definitions in MODULE_SETTING_DEFINITIONS.items():
            for definition in definitions:
                ModuleSetting.objects.update_or_create(
                    module=module,
                    key=definition['key'],
                    defaults={
                        'label': definition['label'],
                        'description': definition.get('description', ''),
                        'default_value': definition['default_value'],
                        'value': definition['default_value'],
                    },
                )

    def test_all_registry_modules_exposed_via_api(self):
        for module in MODULE_SETTING_DEFINITIONS:
            response = self.client.get(f'/api/settings/{module}/')
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f'GET /api/settings/{module}/ failed',
            )
            self.assertEqual(response.data['module'], module)
            for definition in MODULE_SETTING_DEFINITIONS[module]:
                self.assertIn(
                    definition['key'],
                    response.data['settings'],
                    f"missing {module}.{definition['key']}",
                )

    def test_patch_invalidates_and_reenable(self):
        url = '/api/settings/sales/'
        self.client.patch(url, {'show_discount': False}, format='json')
        self.assertFalse(SettingsService.get('sales', 'show_discount'))
        response = self.client.patch(url, {'show_discount': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(SettingsService.get('sales', 'show_discount'))


class StoreAndModuleStatusLayerTests(SuperAdminAPITestCase):
    """Store-wide hide_entity_status_toggles overrides module status in API output."""

    def setUp(self):
        super().setUp()
        _seed_products_settings()
        cat = Category.objects.create(name='Layer Cat', is_active=True)
        self.product = Product.objects.create(
            name='Layer Product',
            sku='P4-LAYER',
            category=cat,
            price=Decimal('20.00'),
            is_active=True,
        )

    def test_hide_entity_status_strips_is_active_from_product_detail(self):
        SettingsService.set('products', 'show_status', True)
        store = StoreSettings.load()
        store.hide_entity_status_toggles = True
        store.save(update_fields=['hide_entity_status_toggles'])

        response = self.client.get(f'/api/products/{self.product.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('is_active', response.data)

        store.hide_entity_status_toggles = False
        store.save(update_fields=['hide_entity_status_toggles'])
        SettingsService.invalidate('products')
        response = self.client.get(f'/api/products/{self.product.id}/')
        self.assertIn('is_active', response.data)
