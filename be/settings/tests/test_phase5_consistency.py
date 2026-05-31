"""Phase 5 — cross-module consistency, impact metadata, and API uniformity."""

from django.core.cache import cache

from settings.models import ModuleSetting
from settings.module_settings_registry import MODULE_SETTING_DEFINITIONS
from settings.settings_service import SettingsService
from utils.tests.api_test_base import SuperAdminAPITestCase


def _registry_high_impact_keys():
    keys = set()
    for module, definitions in MODULE_SETTING_DEFINITIONS.items():
        for definition in definitions:
            if definition.get('impact') == 'high':
                keys.add((module, definition['key']))
    return keys


class ModuleSettingsConsistencyTests(SuperAdminAPITestCase):
    """Registry, API payload shape, and impact metadata stay aligned."""

    def setUp(self):
        super().setUp()
        cache.clear()

    def test_every_registry_key_has_label_and_default(self):
        for module, definitions in MODULE_SETTING_DEFINITIONS.items():
            for definition in definitions:
                self.assertTrue(definition.get('key'))
                self.assertTrue(definition.get('label'))
                self.assertIn('default_value', definition)

    def test_api_returns_impact_for_high_risk_sales_keys(self):
        response = self.client.get('/api/settings/sales/')
        self.assertEqual(response.status_code, 200)
        settings = response.data['settings']
        self.assertEqual(settings['validate_stock_before_sale'].get('impact'), 'high')
        self.assertEqual(settings['show_discount'].get('impact'), 'high')
        self.assertIsNone(settings.get('show_tax', {}).get('impact'))

    def test_api_impact_matches_registry_for_all_modules(self):
        for module in MODULE_SETTING_DEFINITIONS:
            response = self.client.get(f'/api/settings/{module}/')
            self.assertEqual(response.status_code, 200, module)
            registry_by_key = {
                d['key']: d for d in MODULE_SETTING_DEFINITIONS.get(module, [])
            }
            for key, entry in response.data['settings'].items():
                expected = registry_by_key.get(key, {}).get('impact')
                self.assertEqual(entry.get('impact'), expected, f'{module}.{key}')

    def test_high_impact_registry_count_is_stable(self):
        """Guards against accidental removal of impact markers on risky toggles."""
        high_impact = _registry_high_impact_keys()
        self.assertGreaterEqual(len(high_impact), 20)
        self.assertIn(('sales', 'validate_stock_before_sale'), high_impact)
        self.assertIn(('users', 'enable_role_delete'), high_impact)

    def test_settings_service_reads_match_api_values(self):
        ModuleSetting.objects.update_or_create(
            module='products',
            key='show_mrp',
            defaults={
                'label': 'Show MRP',
                'description': '',
                'default_value': True,
                'value': False,
            },
        )
        SettingsService.invalidate('products')
        response = self.client.get('/api/settings/products/')
        self.assertEqual(response.status_code, 200)
        api_value = response.data['settings']['show_mrp']['value']
        service_value = SettingsService.get('products', 'show_mrp', True)
        self.assertFalse(api_value)
        self.assertEqual(api_value, service_value)
