"""Reverse posted journals so corrections stay balanced."""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from unittest.mock import patch

from accounting.models import Account, JournalEntry, Transaction
from accounting.reversal import (
    reverse_posted_transaction,
    reverse_source_documents,
    transaction_is_reversed,
)
from accounting.chart_setup import get_account_type
from rest_framework import status
from utils.tests.api_test_base import SuperAdminAPITestCase


class JournalReversalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('rev_user', password='x')
        asset = get_account_type('asset')
        expense_type = get_account_type('expense')
        cls.cash = Account.objects.create(
            account_code='1000-REV',
            name='Cash Rev',
            account_type=asset,
            is_active=True,
        )
        cls.opex = Account.objects.create(
            account_code='6000-REV',
            name='Opex Rev',
            account_type=expense_type,
            is_active=True,
        )

    def _post_expense_txn(self):
        txn = Transaction.objects.create(
            transaction_date=date.today(),
            description='Posted expense',
            reference='EXP-1',
            reference_type='expense',
            reference_id=91,
            created_by=self.user,
        )
        debit = JournalEntry.objects.create(
            entry_date=date.today(),
            account=self.opex,
            entry_type='debit',
            amount=Decimal('40.00'),
            description='Expense',
            reference='EXP-1',
            reference_type='expense',
            reference_id=91,
            created_by=self.user,
        )
        credit = JournalEntry.objects.create(
            entry_date=date.today(),
            account=self.cash,
            entry_type='credit',
            amount=Decimal('40.00'),
            description='Cash out',
            reference='EXP-1',
            reference_type='expense',
            reference_id=91,
            created_by=self.user,
        )
        txn.journal_entries.add(debit, credit)
        return txn

    def test_requires_reason(self):
        txn = self._post_expense_txn()
        with self.assertRaises(ValidationError):
            reverse_posted_transaction(txn, reason='  ', user=self.user)

    def test_reverses_debits_and_credits(self):
        txn = self._post_expense_txn()
        reverse = reverse_posted_transaction(txn, reason='wrong amount', user=self.user)
        self.assertTrue(reverse.validate_balance())
        self.assertTrue(transaction_is_reversed(txn))
        self.assertEqual(reverse.reference_type, 'reversal')
        self.assertEqual(reverse.reference_id, txn.id)
        types = sorted(reverse.journal_entries.values_list('entry_type', flat=True))
        self.assertEqual(types, ['credit', 'debit'])

    def test_rejects_second_reversal(self):
        txn = self._post_expense_txn()
        reverse_posted_transaction(txn, reason='once', user=self.user)
        with self.assertRaises(ValidationError):
            reverse_posted_transaction(txn, reason='twice', user=self.user)

    def test_rejects_empty_journal(self):
        txn = Transaction.objects.create(
            transaction_date=date.today(),
            description='Empty',
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            reverse_posted_transaction(txn, reason='empty', user=self.user)

    def test_reverse_source_reverses_unreversed(self):
        txn = self._post_expense_txn()
        extra = reverse_source_documents('expense', 91, reason='fix', user=self.user)
        self.assertEqual(len(extra), 1)
        self.assertTrue(transaction_is_reversed(txn))

    def test_rejects_unbalanced_reversal(self):
        txn = self._post_expense_txn()
        with self.assertRaises(ValidationError):
            with patch.object(Transaction, 'validate_balance', return_value=False):
                reverse_posted_transaction(txn, reason='broken', user=self.user)

    def test_reverse_source_skips_already_reversed(self):
        txn = self._post_expense_txn()
        reverse_posted_transaction(txn, reason='first', user=self.user)
        extra = reverse_source_documents('expense', 91, reason='again', user=self.user)
        self.assertEqual(extra, [])


class JournalReversalAPITests(SuperAdminAPITestCase):
    def test_admin_can_reverse_a_transaction(self):
        asset = get_account_type('asset')
        cash = Account.objects.create(
            account_code='1000-API-REV',
            name='Cash API Rev',
            account_type=asset,
        )
        txn = Transaction.objects.create(
            transaction_date=date.today(),
            description='Posted',
            created_by=self.admin,
        )
        debit = JournalEntry.objects.create(
            entry_date=date.today(),
            account=cash,
            entry_type='debit',
            amount=Decimal('12.00'),
            description='Posted debit',
            created_by=self.admin,
        )
        credit = JournalEntry.objects.create(
            entry_date=date.today(),
            account=cash,
            entry_type='credit',
            amount=Decimal('12.00'),
            description='Posted credit',
            created_by=self.admin,
        )
        txn.journal_entries.add(debit, credit)
        resp = self.client.post(
            f'/api/accounting/transactions/{txn.id}/reverse/',
            {'reason': 'wrong posting'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['reference_type'], 'reversal')
