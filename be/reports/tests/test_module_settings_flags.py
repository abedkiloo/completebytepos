"""Unit coverage for reports module setting flags."""

from unittest.mock import patch

from django.test import TestCase

from reports.module_settings import (
    apply_report_response_flags,
    reports_action_enabled,
    reports_action_label,
    reports_enable_cash_reports,
    reports_enable_customer_reports,
    reports_enable_dashboard_summary,
    reports_enable_financial_reports,
    reports_enable_inventory_reports,
    reports_enable_invoice_reports,
    reports_enable_product_reports,
    reports_enable_sales_reports,
    reports_enable_supplier_reports,
    reports_show_cost_and_profit,
    reports_show_discount,
    reports_show_legacy_catalog,
    reports_show_tax,
)
from settings.settings_service import SettingsService


class ReportsModuleSettingsFlagTests(TestCase):
    def tearDown(self):
        for key in (
            'show_discount_in_reports',
            'show_tax_in_reports',
            'show_cost_and_profit',
            'enable_product_reports',
        ):
            SettingsService.set('reports', key, True)
        super().tearDown()

    def test_default_flags_enabled(self):
        SettingsService.set('reports', 'show_discount_in_reports', True)
        SettingsService.set('reports', 'show_tax_in_reports', True)
        SettingsService.set('reports', 'show_cost_and_profit', True)
        self.assertTrue(reports_enable_dashboard_summary())
        self.assertTrue(reports_enable_sales_reports())
        self.assertTrue(reports_enable_product_reports())
        self.assertTrue(reports_enable_inventory_reports())
        self.assertTrue(reports_enable_financial_reports())
        self.assertTrue(reports_enable_invoice_reports())
        self.assertTrue(reports_enable_supplier_reports())
        self.assertTrue(reports_enable_customer_reports())
        self.assertTrue(reports_enable_cash_reports())
        self.assertTrue(reports_show_discount())
        self.assertTrue(reports_show_tax())
        self.assertTrue(reports_show_cost_and_profit())
        self.assertTrue(reports_show_legacy_catalog())

    def test_action_gates(self):
        self.assertTrue(reports_action_enabled('unknown_action'))
        self.assertEqual(reports_action_label('unknown_action'), 'Reports')
        self.assertTrue(reports_action_enabled('trading_profit'))
        self.assertEqual(reports_action_label('trading_profit'), 'Financial reports')
        self.assertEqual(reports_action_label('sales_by_person'), 'Sales reports')

    def test_product_trends_requires_product_reports(self):
        from reports.module_settings import reports_product_trends_enabled

        SettingsService.set('reports', 'enable_product_reports', False)
        self.assertFalse(reports_product_trends_enabled())
        SettingsService.set('reports', 'enable_product_reports', True)
        with patch(
            'reports.product_trends.product_trends_feature_enabled',
            return_value=False,
        ):
            self.assertFalse(reports_product_trends_enabled())
        with patch(
            'reports.product_trends.product_trends_feature_enabled',
            return_value=True,
        ):
            self.assertTrue(reports_product_trends_enabled())

    def test_apply_report_response_flags_strips_sensitive_fields(self):
        SettingsService.set('reports', 'show_discount_in_reports', False)
        SettingsService.set('reports', 'show_tax_in_reports', False)
        SettingsService.set('reports', 'show_cost_and_profit', False)
        payload = {
            'summary': {
                'basis': 'cash',
                'discount_amount': 10,
                'tax_amount': 5,
                'net_profit': 100,
                'total_cogs': 40,
            },
            'tax_breakdown': [{'rate': 16}],
            'growth': {'profit': 1, 'purchase': 2, 'expenses': 3, 'sales': 4},
            'monthly_breakdown': [{'month': 'Jan', 'profit': 9, 'revenue': 1}],
            'monthly_data': [{'month': 'Jan', 'profit': 9, 'sales': 1}],
            'recent_movements': [{'unit_cost': 1, 'total_cost': 2, 'sku': 'A'}],
            'purchases': [{'unit_cost': 1, 'total_cost': 2}],
            'items': [{'unit_cost': 3, 'name': 'x'}],
        }
        out = apply_report_response_flags(payload)
        self.assertNotIn('discount_amount', out['summary'])
        self.assertNotIn('tax_amount', out['summary'])
        self.assertNotIn('net_profit', out['summary'])
        self.assertNotIn('tax_breakdown', out)
        self.assertNotIn('profit', out['growth'])
        self.assertNotIn('profit', out['monthly_breakdown'][0])
        self.assertNotIn('unit_cost', out['recent_movements'][0])
        self.assertNotIn('unit_cost', out['items'][0])
        # Non-dict rows in cost lists stay as-is while dicts are stripped.
        mixed = apply_report_response_flags({
            'summary': {'basis': 'cash'},
            'items': ['skip', {'unit_cost': 9, 'name': 'y'}],
        })
        self.assertEqual(mixed['items'][0], 'skip')
        self.assertNotIn('unit_cost', mixed['items'][1])
        # Trading profit summary is preserved
        trading = apply_report_response_flags({
            'summary': {'basis': 'trading', 'net_profit': 50, 'cogs': 10},
        })
        self.assertEqual(trading['summary']['net_profit'], 50)
        self.assertEqual(apply_report_response_flags('x'), 'x')
