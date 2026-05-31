"""Phase 3 — suppliers module settings gates."""

from decimal import Decimal

from django.core.cache import cache
from rest_framework import status

from settings.models import ModuleSetting, ModuleSettings
from settings.settings_service import SettingsService
from suppliers.models import Supplier
from utils.tests.api_test_base import SuperAdminAPITestCase


def _seed_supplier_settings():
    cache.clear()
    ModuleSettings.objects.update_or_create(
        module_name='suppliers',
        defaults={'description': 'Suppliers', 'is_enabled': True},
    )
    for key, default in (
        ('show_supplier_code', True),
        ('show_supplier_type', True),
        ('show_contact_details', True),
        ('show_business_details', True),
        ('show_payment_terms', True),
        ('show_credit_fields', True),
        ('show_supplier_rating', True),
        ('show_preferred_flag', True),
        ('show_supplier_notes', True),
        ('show_supplier_status', True),
        ('enable_supplier_create', True),
        ('enable_supplier_edit', True),
        ('enable_supplier_delete', True),
        ('enable_supplier_statistics', True),
        ('enable_supplier_products', True),
    ):
        ModuleSetting.objects.update_or_create(
            module='suppliers',
            key=key,
            defaults={
                'label': key,
                'description': '',
                'default_value': default,
                'value': default,
            },
        )


class SupplierModuleSettingsAPITests(SuperAdminAPITestCase):
    base_url = '/api/suppliers/suppliers/'

    def setUp(self):
        super().setUp()
        _seed_supplier_settings()
        self.supplier = Supplier.objects.create(
            name='Flag Vendor',
            supplier_type='business',
            credit_limit=Decimal('10000.00'),
            account_balance=Decimal('2500.00'),
            is_active=True,
        )

    def test_create_forbidden_when_disabled(self):
        SettingsService.set('suppliers', 'enable_supplier_create', False)
        response = self.client.post(self.base_url, {'name': 'New Vendor'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_statistics_forbidden_when_disabled(self):
        SettingsService.set('suppliers', 'enable_supplier_statistics', False)
        response = self.client.get(f'{self.base_url}statistics/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_omits_credit_when_hidden(self):
        SettingsService.set('suppliers', 'show_credit_fields', False)
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', response.data)
        row = next(s for s in rows if s['id'] == self.supplier.id)
        self.assertNotIn('credit_limit', row)
        self.assertNotIn('account_balance', row)

    def test_products_forbidden_when_disabled(self):
        SettingsService.set('suppliers', 'enable_supplier_products', False)
        response = self.client.get(f'{self.base_url}{self.supplier.id}/products/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
