"""Settings architecture — registry integrity and cross-layer rules."""

from django.core.cache import cache

from products.status_rules import products_show_status_enabled
from settings.models import ModuleSetting, StoreSettings
from settings.module_settings_registry import MODULE_SETTING_DEFINITIONS
from settings.settings_service import SettingsService
from utils.tests.api_test_base import SuperAdminAPITestCase


class SettingsArchitectureTests(SuperAdminAPITestCase):
    def test_module_registry_has_phase3_modules(self):
        expected = {
            'products',
            'sales',
            'inventory',
            'customers',
            'employees',
            'suppliers',
            'reports',
            'users',
        }
        self.assertTrue(expected.issubset(set(MODULE_SETTING_DEFINITIONS.keys())))

    def test_registry_definitions_have_unique_keys_per_module(self):
        for module, definitions in MODULE_SETTING_DEFINITIONS.items():
            keys = [d['key'] for d in definitions]
            self.assertEqual(len(keys), len(set(keys)), f'duplicate keys in {module}')

    def test_hide_entity_status_overrides_module_product_status(self):
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
        store = StoreSettings.load()
        store.hide_entity_status_toggles = False
        store.save(update_fields=['hide_entity_status_toggles'])
        SettingsService.invalidate('products')

        self.assertTrue(products_show_status_enabled())

        store.hide_entity_status_toggles = True
        store.save(update_fields=['hide_entity_status_toggles'])
        self.assertFalse(products_show_status_enabled())

        store.hide_entity_status_toggles = False
        store.save(update_fields=['hide_entity_status_toggles'])
        SettingsService.set('products', 'show_status', False)
        self.assertFalse(products_show_status_enabled())
