"""Phase 3 — reports module settings gates."""

from django.core.cache import cache
from rest_framework import status

from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase


def _seed_report_settings():
    cache.clear()
    for key, default in (
        ('enable_dashboard_summary', True),
        ('enable_sales_reports', True),
        ('enable_product_reports', True),
        ('enable_inventory_reports', True),
        ('enable_financial_reports', True),
        ('enable_invoice_reports', True),
        ('enable_supplier_reports', True),
        ('enable_customer_reports', True),
        ('enable_cash_reports', True),
        ('show_discount_in_reports', True),
        ('show_tax_in_reports', True),
        ('show_cost_and_profit', True),
        ('show_legacy_report_catalog', True),
    ):
        ModuleSetting.objects.update_or_create(
            module='reports',
            key=key,
            defaults={
                'label': key,
                'description': '',
                'default_value': default,
                'value': default,
            },
        )


class ReportModuleSettingsAPITests(ManagerAPITestCase):
    base_url = '/api/reports/'

    def setUp(self):
        super().setUp()
        _seed_report_settings()

    def test_dashboard_forbidden_when_disabled(self):
        SettingsService.set('reports', 'enable_dashboard_summary', False)
        response = self.client.get(f'{self.base_url}dashboard/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_overview_forbidden_when_disabled(self):
        SettingsService.set('reports', 'enable_sales_reports', False)
        response = self.client.get(f'{self.base_url}sales_overview/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_overview_omits_discount_when_hidden(self):
        SettingsService.set('reports', 'show_discount_in_reports', False)
        response = self.client.get(f'{self.base_url}sales_overview/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('discount', response.data.get('summary', {}))

    def test_inventory_health_omits_value_when_cost_hidden(self):
        SettingsService.set('reports', 'show_cost_and_profit', False)
        response = self.client.get(f'{self.base_url}inventory_health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('inventory_value', response.data.get('summary', {}))
