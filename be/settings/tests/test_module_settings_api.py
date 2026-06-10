"""Integration tests for GET/PATCH /api/settings/{module}/."""

from django.core.cache import cache
from rest_framework import status

from approvals.models import PendingChange
from settings.models import ModuleSetting, StoreSettings
from settings.module_settings_registry import MODULE_SETTING_DEFINITIONS
from settings.settings_service import SettingsService, coerce_module_setting_value
from utils.tests.api_test_base import ManagerAPITestCase, SuperAdminAPITestCase


class ModuleSettingsAPITests(SuperAdminAPITestCase):
    url = '/api/settings/products/'

    def setUp(self):
        super().setUp()
        cache.clear()
        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled'])
        ModuleSetting.objects.get_or_create(
            module='products',
            key='show_status',
            defaults={
                'label': 'Show product status',
                'description': 'Test',
                'default_value': True,
                'value': True,
            },
        )

    def test_get_module_settings_returns_structure(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['module'], 'products')
        self.assertIn('show_status', response.data['settings'])
        self.assertIn('value', response.data['settings']['show_status'])

    def test_patch_updates_value_and_invalidates_cache(self):
        response = self.client.patch(self.url, {'show_status': False}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['settings']['show_status']['value'])
        self.assertFalse(SettingsService.get('products', 'show_status'))

    def test_patch_reenable_restores_functionality(self):
        self.client.patch(self.url, {'show_status': False}, format='json')
        response = self.client.patch(self.url, {'show_status': True}, format='json')
        self.assertTrue(response.data['settings']['show_status']['value'])
        self.assertTrue(SettingsService.get('products', 'show_status'))

    def test_patch_sales_cost_toggle_persists(self):
        response = self.client.patch(
            self.url,
            {'allow_sales_edit_cost': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['settings']['allow_sales_edit_cost']['value'])
        self.assertTrue(SettingsService.get('products', 'allow_sales_edit_cost'))

    def test_patch_coerces_string_booleans(self):
        response = self.client.patch(
            self.url,
            {'allow_sales_edit_pricing': 'true'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(SettingsService.get('products', 'allow_sales_edit_pricing'))

    def test_patch_with_maker_checker_returns_202_until_approved(self):
        store = StoreSettings.load()
        store.maker_checker_enabled = True
        store.save(update_fields=['maker_checker_enabled'])

        response = self.client.patch(
            self.url,
            {'allow_sales_edit_cost': True, 'reason': 'Enable cost entry for stocktake'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertFalse(SettingsService.get('products', 'allow_sales_edit_cost'))
        self.assertEqual(
            PendingChange.objects.filter(status=PendingChange.STATUS_PENDING).count(),
            1,
        )

    def test_patch_with_maker_checker_requires_reason(self):
        store = StoreSettings.load()
        store.maker_checker_enabled = True
        store.save(update_fields=['maker_checker_enabled'])

        response = self.client.patch(
            self.url,
            {'allow_sales_edit_cost': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('reason', response.data)


class CoerceModuleSettingValueTests(SuperAdminAPITestCase):
    def test_coerce_module_setting_value(self):
        self.assertTrue(coerce_module_setting_value(True))
        self.assertFalse(coerce_module_setting_value('false'))
        self.assertTrue(coerce_module_setting_value('1'))
        self.assertEqual(coerce_module_setting_value('maybe'), 'maybe')


class ModuleSettingsRegistrySalesDefaultsTests(SuperAdminAPITestCase):
    def test_registry_sales_financial_flags_default_false(self):
        by_key = {d['key']: d for d in MODULE_SETTING_DEFINITIONS['products']}
        self.assertFalse(by_key['allow_sales_edit_pricing']['default_value'])
        self.assertFalse(by_key['allow_sales_edit_cost']['default_value'])


class ModuleSettingsAPIPermissionTests(ManagerAPITestCase):
    url = '/api/settings/products/'

    def test_manager_can_read(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_manager_cannot_patch(self):
        response = self.client.patch(self.url, {'show_status': False}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
