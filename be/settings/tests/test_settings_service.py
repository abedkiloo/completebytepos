"""Unit tests for SettingsService and module settings cache."""

from django.core.cache import cache
from django.test import TestCase

from settings.models import ModuleSetting
from settings.settings_service import SettingsService


class SettingsServiceUnitTests(TestCase):
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

    def test_get_returns_value_when_set(self):
        SettingsService.set('products', 'show_status', False)
        self.assertFalse(SettingsService.get('products', 'show_status'))

    def test_get_returns_default_when_not_set(self):
        self.assertTrue(SettingsService.get('products', 'missing_key', default=True))

    def test_get_module_returns_dict(self):
        module = SettingsService.get_module('products')
        self.assertIn('show_status', module)
        self.assertTrue(module['show_status'])

    def test_set_invalidates_cache(self):
        SettingsService.get('products', 'show_status')
        SettingsService.set('products', 'show_status', False)
        self.assertFalse(SettingsService.get('products', 'show_status'))

    def test_set_many_updates_rows(self):
        SettingsService.set_many('products', {'show_status': False})
        row = ModuleSetting.objects.get(module='products', key='show_status')
        self.assertFalse(row.value)
