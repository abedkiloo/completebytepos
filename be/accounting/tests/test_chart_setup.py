"""Unit tests for default chart of accounts setup."""

from django.test import TestCase

from accounting.chart_setup import (
    DEFAULT_ACCOUNT_TYPES,
    ensure_default_account_types,
    get_account_type,
)
from accounting.models import AccountType


class ChartSetupTests(TestCase):
    def test_ensure_default_account_types_creates_all_five(self):
        self.assertEqual(AccountType.objects.count(), 0)
        result = ensure_default_account_types()
        self.assertEqual(len(result), 5)
        self.assertEqual(AccountType.objects.count(), 5)
        for spec in DEFAULT_ACCOUNT_TYPES:
            self.assertIn(spec['name'], result)
            self.assertEqual(result[spec['name']].normal_balance, spec['normal_balance'])

    def test_ensure_default_account_types_is_idempotent(self):
        ensure_default_account_types()
        ensure_default_account_types()
        self.assertEqual(AccountType.objects.count(), 5)

    def test_get_account_type_creates_single_type(self):
        asset = get_account_type('asset')
        self.assertEqual(asset.name, 'asset')
        self.assertEqual(asset.normal_balance, 'debit')
        self.assertEqual(AccountType.objects.count(), 1)

    def test_get_account_type_unknown_raises(self):
        with self.assertRaises(ValueError):
            get_account_type('not_a_type')
