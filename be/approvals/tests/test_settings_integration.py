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
    sensitive_store_keys_that_changed,
    store_setting_values_equal,
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

    def test_backfill_limit_is_immediate(self):
        self.assertIn('backfill_max_days', STORE_SETTINGS_IMMEDIATE_FIELDS)
        self.assertIn('backfill_maker_checker_enabled', STORE_SETTINGS_IMMEDIATE_FIELDS)

    def test_sensitive_keys_ignore_unchanged_submitted_values(self):
        class Store:
            receipt_footer_text = 'Thanks'
            enabled_payment_methods = ['cash']
            allow_sales_add_products = True
            backfill_max_days = 0

        changed = sensitive_store_keys_that_changed(
            Store(),
            {
                'backfill_max_days': 90,
                'receipt_footer_text': 'Thanks',
                'enabled_payment_methods': ['cash'],
                'allow_sales_add_products': True,
            },
            {
                'backfill_max_days',
                'receipt_footer_text',
                'enabled_payment_methods',
                'allow_sales_add_products',
                'reason',
            },
        )
        self.assertEqual(changed, set())

    def test_sensitive_keys_detect_receipt_change(self):
        class Store:
            receipt_footer_text = 'Old'

        changed = sensitive_store_keys_that_changed(
            Store(),
            {'receipt_footer_text': 'New'},
            {'receipt_footer_text'},
        )
        self.assertEqual(changed, {'receipt_footer_text'})

    def test_payment_method_list_equality(self):
        self.assertTrue(
            store_setting_values_equal(
                'enabled_payment_methods', ['cash', 'mpesa'], ['cash', 'mpesa']
            )
        )
        self.assertFalse(
            store_setting_values_equal(
                'enabled_payment_methods', ['cash'], ['cash', 'mpesa']
            )
        )
