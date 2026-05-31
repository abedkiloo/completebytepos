"""Phase 3 — customers module settings gates."""

from decimal import Decimal

from django.core.cache import cache
from rest_framework import status

from sales.models import Customer
from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase


def _seed_customer_settings():
    cache.clear()
    for key, default in (
        ('show_customer_code', True),
        ('show_outstanding_balance', True),
        ('show_wallet_balance', True),
        ('enable_customer_create', True),
        ('enable_customer_edit', True),
        ('enable_customer_delete', True),
        ('show_customer_type', True),
        ('show_tax_id', True),
        ('show_customer_notes', True),
        ('show_customer_status', True),
        ('allow_quick_add_at_pos', True),
    ):
        ModuleSetting.objects.update_or_create(
            module='customers',
            key=key,
            defaults={
                'label': key,
                'description': '',
                'default_value': default,
                'value': default,
            },
        )


class CustomerModuleSettingsAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_customer_settings()
        self.customer = Customer.objects.create(
            name='Flagged Customer',
            email='flag@test.com',
            phone='0700000000',
            wallet_balance=Decimal('50.00'),
            is_active=True,
        )

    def test_create_forbidden_when_disabled(self):
        SettingsService.set('customers', 'enable_customer_create', False)
        response = self.client.post(
            '/api/sales/customers/',
            {'name': 'New One'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_forbidden_when_disabled(self):
        SettingsService.set('customers', 'enable_customer_delete', False)
        response = self.client.delete(f'/api/sales/customers/{self.customer.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_omits_wallet_when_hidden(self):
        SettingsService.set('customers', 'show_wallet_balance', False)
        response = self.client.get('/api/sales/customers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', response.data)
        row = next(c for c in rows if c['id'] == self.customer.id)
        self.assertNotIn('wallet_balance', row)

    def test_list_omits_outstanding_when_hidden(self):
        SettingsService.set('customers', 'show_outstanding_balance', False)
        response = self.client.get('/api/sales/customers/')
        row = next(
            c for c in response.data.get('results', response.data) if c['id'] == self.customer.id
        )
        self.assertNotIn('total_outstanding', row)
