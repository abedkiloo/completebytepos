"""Integration tests for accounting report endpoints."""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status

from accounting.models import Account, AccountType, JournalEntry
from accounting.chart_setup import get_account_type
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class AccountingReportAPITests(ManagerAPITestCase):
    balance_sheet_url = '/api/accounting/reports/balance_sheet/'
    income_statement_url = '/api/accounting/reports/income_statement/'
    trial_balance_url = '/api/accounting/reports/trial_balance/'

    def test_balance_sheet_requires_authentication(self):
        self.client.credentials()
        response = self.client.get(self.balance_sheet_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_balance_sheet_without_prior_init_accounts(self):
        """Regression: must not 500 when AccountType rows are missing."""
        self.assertEqual(AccountType.objects.count(), 0)
        response = self.client.get(self.balance_sheet_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(AccountType.objects.count(), 5)
        self.assertIn('assets', response.data)
        self.assertIn('liabilities', response.data)
        self.assertIn('equity', response.data)
        self.assertEqual(float(response.data['total_assets']), 0.0)
        self.assertEqual(float(response.data['total_liabilities']), 0.0)
        self.assertEqual(float(response.data['total_equity']), 0.0)
        self.assertIn('date', response.data)

    def test_balance_sheet_reflects_asset_journal_entries(self):
        asset_type = get_account_type('asset')
        cash = Account.objects.create(
            account_code='1000',
            name='Cash',
            account_type=asset_type,
            opening_balance=Decimal('500.00'),
        )
        user = User.objects.get(username='phase2_manager')
        JournalEntry.objects.create(
            entry_date=date.today(),
            account=cash,
            entry_type='debit',
            amount=Decimal('200.00'),
            description='Test deposit',
            created_by=user,
        )

        response = self.client.get(self.balance_sheet_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Cash', response.data['assets'])
        self.assertEqual(response.data['assets']['Cash']['balance'], 700.0)
        self.assertEqual(float(response.data['total_assets']), 700.0)

    def test_balance_sheet_includes_retained_earnings_from_pnl(self):
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
        JournalEntry.objects.create(
            entry_date=date.today(),
            account=sales,
            entry_type='credit',
            amount=Decimal('1000.00'),
            description='Sales',
            created_by=user,
        )
        JournalEntry.objects.create(
            entry_date=date.today(),
            account=opex,
            entry_type='debit',
            amount=Decimal('400.00'),
            description='Rent',
            created_by=user,
        )

        response = self.client.get(self.balance_sheet_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Retained Earnings', response.data['equity'])
        self.assertEqual(response.data['equity']['Retained Earnings']['balance'], 600.0)
        self.assertEqual(float(response.data['total_equity']), 600.0)

    def test_income_statement_without_prior_init_accounts(self):
        self.assertEqual(AccountType.objects.count(), 0)
        response = self.client.get(self.income_statement_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(AccountType.objects.count(), 5)
        self.assertEqual(float(response.data['total_revenue']), 0.0)
        self.assertEqual(float(response.data['total_expenses']), 0.0)
        self.assertEqual(float(response.data['net_income']), 0.0)

    def test_income_statement_totals(self):
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
        JournalEntry.objects.create(
            entry_date=date.today(),
            account=sales,
            entry_type='credit',
            amount=Decimal('800.00'),
            description='Sales',
            created_by=user,
        )
        JournalEntry.objects.create(
            entry_date=date.today(),
            account=opex,
            entry_type='debit',
            amount=Decimal('300.00'),
            description='Utilities',
            created_by=user,
        )

        response = self.client.get(self.income_statement_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['total_revenue']), 800.0)
        self.assertEqual(float(response.data['total_expenses']), 300.0)
        self.assertEqual(float(response.data['net_income']), 500.0)

    def test_trial_balance_empty(self):
        response = self.client.get(self.trial_balance_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['accounts'], [])
        self.assertEqual(float(response.data['total_debits']), 0.0)
        self.assertEqual(float(response.data['total_credits']), 0.0)


class AccountingReportSalesAccessTests(SalesAPITestCase):
    balance_sheet_url = '/api/accounting/reports/balance_sheet/'

    def test_sales_cannot_access_balance_sheet(self):
        response = self.client.get(self.balance_sheet_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
