"""init_module_settings must seed new keys without overwriting live values."""

from io import StringIO

from django.core.management import call_command

from settings.models import ModuleSetting
from settings.module_settings_registry import MODULE_SETTING_DEFINITIONS
from utils.tests.api_test_base import SuperAdminAPITestCase


class InitModuleSettingsCommandTests(SuperAdminAPITestCase):
    def test_sync_preserves_existing_value_on_rerun(self):
        ModuleSetting.objects.update_or_create(
            module='products',
            key='allow_sales_edit_cost',
            defaults={
                'label': 'Sales: set cost of goods',
                'description': 'Test',
                'default_value': False,
                'value': True,
                'display_order': 23,
            },
        )

        out = StringIO()
        call_command('init_module_settings', stdout=out)

        row = ModuleSetting.objects.get(module='products', key='allow_sales_edit_cost')
        self.assertTrue(row.value)
        self.assertIn('Module settings sync complete', out.getvalue())

    def test_sync_creates_missing_keys_with_registry_defaults(self):
        ModuleSetting.objects.filter(module='products', key='allow_sales_edit_pricing').delete()

        call_command('init_module_settings', stdout=StringIO())

        row = ModuleSetting.objects.get(module='products', key='allow_sales_edit_pricing')
        definition = next(
            d
            for d in MODULE_SETTING_DEFINITIONS['products']
            if d['key'] == 'allow_sales_edit_pricing'
        )
        self.assertEqual(row.value, definition['default_value'])
        self.assertFalse(row.value)


class SalesCatalogDefaultTests(SuperAdminAPITestCase):
    def test_sales_pricing_and_cost_default_off_in_registry(self):
        products = {d['key']: d['default_value'] for d in MODULE_SETTING_DEFINITIONS['products']}
        self.assertFalse(products['allow_sales_edit_pricing'])
        self.assertFalse(products['allow_sales_edit_cost'])
        self.assertFalse(products['allow_sales_edit_stock'])
