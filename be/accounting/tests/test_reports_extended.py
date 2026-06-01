"""Extended accounting report endpoints — ledger, cash flow, statements."""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status

from accounting.chart_setup import get_account_type
from accounting.models import Account, JournalEntry
from utils.tests.api_test_base import ManagerAPITestCase


class AccountingExtendedReportTests(ManagerAPITestCase):
    ledger_url = '/api/accounting/reports/general_ledger/'
    cash_flow_url = '/api/accounting/reports/cash_flow/'
    statement_url = '/api/accounting/reports/account_statement/'
    trial_balance_url = '/api/accounting/reports/trial_balance/'

    def _cash_account(self):
        return Account.objects.create(
            account_code='1000',
            name='Cash',
            account_type=get_account_type('asset'),
            opening_balance=Decimal('1000.00'),
        )

    def test_general_ledger_requires_account_id(self):
        response = self.client.get(self.ledger_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('account_id', response.data['error'])

    def test_general_ledger_running_balance(self):
        cash = self._cash_account()
        user = User.objects.get(username='phase2_manager')
        JournalEntry.objects.create(
            entry_date=date.today(),
            account=cash,
            entry_type='debit',
            amount=Decimal('150.00'),
            description='Deposit',
            created_by=user,
        )
        JournalEntry.objects.create(
            entry_date=date.today(),
            account=cash,
            entry_type='credit',
            amount=Decimal('40.00'),
            description='Withdrawal',
            created_by=user,
        )

        response = self.client.get(self.ledger_url, {'account_id': cash.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['entries']), 2)
        self.assertEqual(response.data['closing_balance'], 1110.0)

    def test_cash_flow_defaults_without_accounts(self):
        response = self.client.get(self.cash_flow_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('operating_activities', response.data)
        self.assertEqual(response.data['net_cash_flow'], 0.0)

    def test_cash_flow_reflects_sales_and_expense_accounts(self):
        revenue_type = get_account_type('revenue')
        expense_type = get_account_type('expense')
        sales = Account.objects.create(
            account_code='4000',
            name='Sales Revenue',
            account_type=revenue_type,
        )
        opex = Account.objects.create(
            account_code='6000',
            name='Operating Expenses',
            account_type=expense_type,
        )
        user = User.objects.get(username='phase2_manager')
        today = date.today()
        JournalEntry.objects.create(
            entry_date=today,
            account=sales,
            entry_type='credit',
            amount=Decimal('500.00'),
            description='Sales',
            created_by=user,
        )
        JournalEntry.objects.create(
            entry_date=today,
            account=opex,
            entry_type='debit',
            amount=Decimal('120.00'),
            description='Utilities',
            created_by=user,
        )

        response = self.client.get(
            self.cash_flow_url,
            {
                'date_from': today.isoformat(),
                'date_to': today.isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['operating_activities']['cash_from_sales'], 500.0)
        self.assertEqual(response.data['operating_activities']['cash_paid_expenses'], 120.0)
        self.assertEqual(response.data['net_cash_flow'], 380.0)

    def test_account_statement_matches_ledger_shape(self):
        cash = self._cash_account()
        user = User.objects.get(username='phase2_manager')
        JournalEntry.objects.create(
            entry_date=date.today(),
            account=cash,
            entry_type='debit',
            amount=Decimal('200.00'),
            description='Top-up',
            created_by=user,
        )

        response = self.client.get(self.statement_url, {'account_id': cash.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['account']['account_code'], '1000')
        self.assertEqual(len(response.data['entries']), 1)
        self.assertEqual(response.data['closing_balance'], 1200.0)

    def test_trial_balance_with_mixed_entries(self):
        asset_type = get_account_type('asset')
        revenue_type = get_account_type('revenue')
        cash = Account.objects.create(
            account_code='1010',
            name='Petty Cash',
            account_type=asset_type,
            opening_balance=Decimal('0'),
        )
        sales = Account.objects.create(
            account_code='4010',
            name='Retail Sales',
            account_type=revenue_type,
        )
        user = User.objects.get(username='phase2_manager')
        JournalEntry.objects.create(
            entry_date=date.today(),
            account=cash,
            entry_type='debit',
            amount=Decimal('300.00'),
            description='Sale cash',
            created_by=user,
        )
        JournalEntry.objects.create(
            entry_date=date.today(),
            account=sales,
            entry_type='credit',
            amount=Decimal('300.00'),
            description='Sale revenue',
            created_by=user,
        )

        response = self.client.get(self.trial_balance_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['total_debits']), float(response.data['total_credits']))
