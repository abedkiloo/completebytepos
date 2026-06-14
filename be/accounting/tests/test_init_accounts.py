"""Tests for the init_accounts management command."""

from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from accounting.models import Account, AccountType


class InitAccountsCommandTests(TestCase):
    def test_init_accounts_creates_fifteen_standard_accounts(self):
        call_command('init_accounts')
        self.assertEqual(AccountType.objects.count(), 5)
        self.assertEqual(Account.objects.count(), 15)
        codes = sorted(Account.objects.values_list('account_code', flat=True))
        self.assertEqual(
            codes,
            [
                '1000', '1100', '1200', '1300', '2000', '2100', '3000', '3100',
                '4000', '4100', '5000', '6000', '6100', '6200', '6300',
            ],
        )

    def test_init_accounts_is_idempotent(self):
        call_command('init_accounts')
        call_command('init_accounts')
        self.assertEqual(Account.objects.count(), 15)

    def test_init_accounts_links_correct_account_types(self):
        call_command('init_accounts')
        inventory = Account.objects.get(account_code='1300')
        revenue = Account.objects.get(account_code='4000')
        self.assertEqual(inventory.account_type.name, 'asset')
        self.assertEqual(revenue.account_type.name, 'revenue')
        self.assertEqual(inventory.opening_balance, Decimal('0.00'))
        self.assertEqual(inventory.current_balance, Decimal('0.00'))
