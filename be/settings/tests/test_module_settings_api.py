"""Integration tests for GET/PATCH /api/settings/{module}/."""

from django.core.cache import cache
from rest_framework import status

from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase, SuperAdminAPITestCase


class ModuleSettingsAPITests(SuperAdminAPITestCase):
    url = '/api/settings/products/'

    def setUp(self):
        super().setUp()
        cache.clear()
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


class ModuleSettingsAPIPermissionTests(ManagerAPITestCase):
    url = '/api/settings/products/'

    def test_manager_can_read(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_manager_cannot_patch(self):
        response = self.client.patch(self.url, {'show_status': False}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
