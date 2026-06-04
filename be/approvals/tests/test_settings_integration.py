"""Unit tests for P2 settings integration helpers."""

from django.test import TestCase

from approvals.registry import (
    ACTION_PAYMENT_METHODS,
    ACTION_RECEIPT_LEGAL,
    ACTION_STORE_SETTINGS,
)
from approvals.settings_integration import (
    STORE_SETTINGS_IMMEDIATE_FIELDS,
    classify_store_settings_changes,
)


class SettingsIntegrationUnitTests(TestCase):
    def test_immediate_fields_excluded_from_pending(self):
        validated = {
            'maker_checker_enabled': False,
            'enabled_payment_methods': ['cash'],
        }
        grouped = classify_store_settings_changes(
            validated,
            submitted_keys=set(validated.keys()),
        )
        self.assertIn(ACTION_PAYMENT_METHODS, grouped)
        self.assertNotIn('maker_checker_enabled', grouped[ACTION_PAYMENT_METHODS])

    def test_classifies_receipt_and_store_rules(self):
        validated = {
            'receipt_footer_text': 'Thanks',
            'allow_sales_add_products': True,
        }
        grouped = classify_store_settings_changes(
            validated,
            submitted_keys={'receipt_footer_text', 'allow_sales_add_products'},
        )
        self.assertEqual(grouped[ACTION_RECEIPT_LEGAL]['receipt_footer_text'], 'Thanks')
        self.assertTrue(grouped[ACTION_STORE_SETTINGS]['allow_sales_add_products'])

    def test_maker_checker_fields_are_immediate(self):
        self.assertIn('maker_checker_enabled', STORE_SETTINGS_IMMEDIATE_FIELDS)
