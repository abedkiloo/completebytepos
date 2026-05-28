from django.contrib.auth.models import User
from django.test import TestCase

from settings.models import ModuleSettings
from settings.module_catalog import apply_module_preset, build_modules_response
from settings.module_registry import resolve_preset, MODULE_BY_NAME, PRESETS


class ModuleRegistryTests(TestCase):
    def setUp(self):
        from django.core.management import call_command

        call_command('init_modules', verbosity=0)

    def test_resolve_preset_merges_extends(self):
        starter = resolve_preset('retail_starter')
        self.assertTrue(starter['modules']['sales'])
        self.assertIn('billing_pos', starter['features']['sales'])
        self.assertNotIn('pos', starter['features']['sales'])
        self.assertNotIn('normal_sale', starter['features']['sales'])
        self.assertTrue(starter['modules']['invoicing'])
        self.assertIn('invoice_creation', starter['features']['invoicing'])

        full = resolve_preset('retail_full')
        self.assertTrue(full['modules']['reports'])
        self.assertTrue(full['modules']['sales'])
        self.assertIn('pos', full['features']['sales'])

    def test_build_response_has_catalog_and_meta(self):
        data = build_modules_response()
        self.assertIn('catalog', data)
        self.assertIn('_meta', data)
        self.assertTrue(len(data['catalog']) >= 5)
        self.assertTrue(data['_meta'].get('presets'))

    def test_apply_retail_starter_disables_legacy_accounting_satellites(self):
        user = User.objects.create_user('admin', password='x')
        apply_module_preset('retail_starter', user=user)
        accounting = ModuleSettings.objects.get(module_name='accounting')
        self.assertFalse(accounting.is_enabled)
        sales = ModuleSettings.objects.get(module_name='sales')
        self.assertTrue(sales.is_enabled)
        pos = sales.features.get(feature_key='pos')
        self.assertFalse(pos.is_enabled)
        billing = sales.features.get(feature_key='billing_pos')
        self.assertTrue(billing.is_enabled)
        barcodes = ModuleSettings.objects.get(module_name='barcodes')
        self.assertFalse(barcodes.is_enabled)
        invoicing = ModuleSettings.objects.get(module_name='invoicing')
        self.assertTrue(invoicing.is_enabled)
        self.assertTrue(
            invoicing.features.get(feature_key='invoice_creation').is_enabled
        )

    def test_all_registry_modules_exist_after_init(self):
        for name in MODULE_BY_NAME:
            self.assertTrue(
                ModuleSettings.objects.filter(module_name=name).exists(),
                msg=f'missing module {name}',
            )

    def test_preset_ids_are_documented(self):
        self.assertIn('retail_starter', PRESETS)
        self.assertIn('retail_full', PRESETS)
