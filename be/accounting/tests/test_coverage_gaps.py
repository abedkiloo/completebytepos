"""Focused coverage for accounting services, models, and report edge paths."""

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework import status

from accounting.chart_setup import get_account_type
from accounting.models import Account, AccountType, JournalEntry, Transaction
from accounting.services import (
    AccountService,
    AccountTypeService,
    JournalEntryService,
    TransactionService,
    create_expense_journal_entry,
    create_income_journal_entry,
    create_sale_journal_entry,
    create_sale_refund_journal_entry,
    sale_books_date,
)
from accounting import views as accounting_views
from utils.tests.api_test_base import ManagerAPITestCase


class SaleBooksDateTests(SimpleTestCase):
    def test_sale_books_date_variants(self):
        self.assertEqual(
            sale_books_date(SimpleNamespace(occurred_at=None, created_at=None)),
            timezone.localdate(),
        )
        naive = datetime(2026, 3, 15, 10, 0, 0)
        self.assertEqual(
            sale_books_date(SimpleNamespace(occurred_at=naive, created_at=None)),
            date(2026, 3, 15),
        )
        aware = timezone.make_aware(datetime(2026, 4, 1, 22, 0, 0))
        self.assertEqual(
            sale_books_date(SimpleNamespace(occurred_at=aware, created_at=None)),
            timezone.localtime(aware).date(),
        )
        self.assertEqual(
            sale_books_date(SimpleNamespace(occurred_at=date(2026, 5, 1), created_at=None)),
            date(2026, 5, 1),
        )
        self.assertEqual(
            sale_books_date(SimpleNamespace(occurred_at='weird', created_at=None)),
            timezone.localdate(),
        )


class AccountingServiceQuerysetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('acct_svc', password='x')
        self.asset = AccountType.objects.create(name='asset', normal_balance='debit')
        self.cash = Account.objects.create(
            account_code='1000', name='Cash', account_type=self.asset, is_active=True,
        )
        self.bank = Account.objects.create(
            account_code='1100', name='Bank', account_type=self.asset, is_active=False,
        )
        self.je = JournalEntry.objects.create(
            entry_date=date.today(),
            account=self.cash,
            entry_type='debit',
            amount=Decimal('10.00'),
            description='Seed',
            created_by=self.user,
        )
        self.txn = Transaction.objects.create(
            transaction_date=date.today(),
            description='Seed txn',
            created_by=self.user,
        )
        self.txn.journal_entries.add(self.je)

    def test_account_type_and_account_filters(self):
        types = AccountTypeService().build_queryset()
        self.assertTrue(types.exists())

        svc = AccountService()
        self.assertEqual(svc.build_queryset().count(), 2)
        self.assertEqual(svc.build_queryset({'account_type': 'asset'}).count(), 2)
        self.assertEqual(svc.build_queryset({'is_active': 'true'}).count(), 1)
        self.assertEqual(svc.build_queryset({'is_active': False}).count(), 1)
        updated = svc.update_balance(self.cash)
        self.assertEqual(updated.current_balance, Decimal('10.00'))

    def test_journal_and_transaction_filters(self):
        je_svc = JournalEntryService()
        self.assertTrue(je_svc.build_queryset().exists())
        self.assertEqual(je_svc.build_queryset({'account': self.cash.id}).count(), 1)
        self.assertEqual(je_svc.build_queryset({'account': 'bad'}).count(), 0)
        self.assertEqual(
            je_svc.build_queryset({
                'date_from': date.today().isoformat(),
                'date_to': date.today().isoformat(),
                'entry_type': 'debit',
            }).count(),
            1,
        )

        txn_svc = TransactionService()
        self.assertTrue(txn_svc.build_queryset().exists())
        self.assertEqual(
            txn_svc.build_queryset({
                'date_from': date.today().isoformat(),
                'date_to': date.today().isoformat(),
            }).count(),
            1,
        )


class AccountingModelTests(TestCase):
    def test_str_balance_save_delete(self):
        at = AccountType(name='liability')
        at.save()  # auto normal_balance credit
        self.assertEqual(at.normal_balance, 'credit')
        self.assertEqual(str(at), 'liability')

        expense_type = AccountType(name='expense')
        expense_type.save()
        self.assertEqual(expense_type.normal_balance, 'debit')

        acct = Account.objects.create(
            account_code='2000', name='AP', account_type=at, opening_balance=Decimal('5'),
        )
        self.assertIn('2000', str(acct))
        self.assertEqual(acct.balance, acct.current_balance)

        je = JournalEntry.objects.create(
            entry_date=date.today(),
            account=acct,
            entry_type='credit',
            amount=Decimal('3.00'),
            description='Credit AP',
        )
        self.assertIn(je.entry_number, str(je))
        acct.refresh_from_db()
        self.assertEqual(acct.current_balance, Decimal('8.00'))

        je.delete()
        acct.refresh_from_db()
        self.assertEqual(acct.current_balance, Decimal('5.00'))

        txn = Transaction.objects.create(
            transaction_date=date.today(),
            description='Balanced',
        )
        self.assertIn(txn.transaction_number, str(txn))
        self.assertTrue(txn.validate_balance())


class AccountingJournalHelpersTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('acct_je', password='x')

    def test_expense_income_wrappers_and_invoice_payment(self):
        expense = SimpleNamespace(
            payment_method='cash',
            expense_date=date.today(),
            description='Rent',
            expense_number='EXP-1',
            id=1,
            created_by=self.user,
            amount=Decimal('100.00'),
        )
        # Patch amount access used in service — read create_expense_journal_entry
        expense.amount = Decimal('100.00')
        txn = create_expense_journal_entry(expense)
        self.assertEqual(txn.reference_type, 'expense')

        expense_bank = SimpleNamespace(
            payment_method='mpesa',
            expense_date=date.today(),
            description='Fuel',
            expense_number='EXP-2',
            id=2,
            created_by=self.user,
            amount=Decimal('50.00'),
        )
        txn2 = create_expense_journal_entry(expense_bank)
        self.assertEqual(txn2.reference_type, 'expense')

        income = SimpleNamespace(
            payment_method='cash',
            income_date=date.today(),
            description='Other',
            income_number='INC-1',
            id=1,
            created_by=self.user,
            amount=Decimal('40.00'),
        )
        create_income_journal_entry(income)
        income_bank = SimpleNamespace(
            payment_method='bank',
            income_date=date.today(),
            description='Other2',
            income_number='INC-2',
            id=2,
            created_by=self.user,
            amount=Decimal('40.00'),
        )
        create_income_journal_entry(income_bank)

        # view wrappers
        accounting_views.create_expense_journal_entry(expense_bank)
        accounting_views.create_income_journal_entry(income_bank)

        invoice = SimpleNamespace(
            sale=SimpleNamespace(id=1),
            invoice_number='INV-1',
            id=1,
        )
        self.assertIsNone(accounting_views.create_invoice_journal_entry(invoice))

        invoice2 = SimpleNamespace(
            sale=None,
            invoice_number='INV-2',
            id=2,
            issued_date=date.today(),
            total=Decimal('75.00'),
            created_by=self.user,
        )
        txn_inv = accounting_views.create_invoice_journal_entry(invoice2)
        self.assertEqual(txn_inv.reference_type, 'invoice')

        payment_cash = SimpleNamespace(
            invoice=invoice2,
            payment_method='cash',
            payment_date=date.today(),
            amount=Decimal('20.00'),
            reference='P1',
            id=1,
            recorded_by=self.user,
        )
        accounting_views.create_payment_journal_entry(payment_cash)
        payment_bank = SimpleNamespace(
            invoice=invoice2,
            payment_method='mpesa',
            payment_date=date.today(),
            amount=Decimal('10.00'),
            reference='',
            id=2,
            recorded_by=self.user,
        )
        accounting_views.create_payment_journal_entry(payment_bank)

    def test_sale_journal_and_refund(self):
        from sales.models import Sale

        real = Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('100'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('100'),
            amount_paid=Decimal('100'),
            cashier=self.user,
            served_by=self.user,
        )
        accounting_views.create_sale_journal_entry(real)
        self.assertIsNotNone(create_sale_journal_entry(real))

        holding = Sale.objects.create(
            status='holding',
            payment_method='cash',
            subtotal=Decimal('10'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('10'),
            amount_paid=Decimal('10'),
            cashier=self.user,
            served_by=self.user,
        )
        self.assertIsNone(create_sale_journal_entry(holding))

        refund = SimpleNamespace(
            sale=real,
            amount=Decimal('0'),
            refund_number='RF-0',
            id=1,
            created_at=timezone.now(),
            refunded_by=self.user,
        )
        self.assertIsNone(create_sale_refund_journal_entry(refund))

        refund2 = SimpleNamespace(
            sale=real,
            amount=Decimal('10.00'),
            refund_number='RF-1',
            id=2,
            created_at=timezone.now(),
            refunded_by=self.user,
        )
        with patch(
            'sales.refund_allocation.compute_refund_allocation',
            return_value={
                'cash_back': Decimal('10.00'),
                'wallet_back': Decimal('0'),
                'debt_back': Decimal('0'),
            },
        ):
            self.assertIsNotNone(create_sale_refund_journal_entry(refund2))


class AccountingAPICoverageTests(ManagerAPITestCase):
    def test_account_filters_update_balance_and_pdfs(self):
        asset = get_account_type('asset')
        liability = get_account_type('liability')
        equity = get_account_type('equity')
        cash = Account.objects.create(
            account_code='1000', name='Cash', account_type=asset,
            opening_balance=Decimal('100'),
        )
        ap = Account.objects.create(
            account_code='2000', name='AP', account_type=liability,
            opening_balance=Decimal('40'),
        )
        equity_acct = Account.objects.create(
            account_code='3000', name='Capital', account_type=equity,
            opening_balance=Decimal('60'),
        )
        user = User.objects.get(username='phase2_manager')
        JournalEntry.objects.create(
            entry_date=date.today(),
            account=cash,
            entry_type='debit',
            amount=Decimal('20.00'),
            description='In',
            created_by=user,
        )
        JournalEntry.objects.create(
            entry_date=date.today(),
            account=ap,
            entry_type='credit',
            amount=Decimal('10.00'),
            description='AP',
            created_by=user,
        )
        JournalEntry.objects.create(
            entry_date=date.today(),
            account=equity_acct,
            entry_type='credit',
            amount=Decimal('5.00'),
            description='Cap',
            created_by=user,
        )

        listed = self.client.get('/api/accounting/accounts/', {'is_active': 'true'})
        self.assertEqual(listed.status_code, status.HTTP_200_OK)

        bal = self.client.post(f'/api/accounting/accounts/{cash.id}/update_balance/')
        self.assertIn(bal.status_code, (status.HTTP_200_OK, status.HTTP_403_FORBIDDEN))

        types = self.client.get('/api/accounting/account-types/')
        self.assertEqual(types.status_code, status.HTTP_200_OK)

        je = self.client.get(
            '/api/accounting/journal-entries/',
            {
                'account': cash.id,
                'date_from': date.today().isoformat(),
                'date_to': date.today().isoformat(),
                'entry_type': 'debit',
            },
        )
        self.assertEqual(je.status_code, status.HTTP_200_OK)

        txns = self.client.get(
            '/api/accounting/transactions/',
            {
                'date_from': date.today().isoformat(),
                'date_to': date.today().isoformat(),
            },
        )
        self.assertEqual(txns.status_code, status.HTTP_200_OK)

        from io import BytesIO

        fake_pdf = BytesIO(b'%PDF-1.4 fake')
        with patch('accounting.views.create_balance_sheet_pdf', return_value=fake_pdf):
            bs = self.client.get(
                '/api/accounting/reports/balance_sheet/',
                {'date': date.today().isoformat(), 'format': 'pdf'},
            )
            self.assertEqual(bs.status_code, status.HTTP_200_OK)
            self.assertEqual(bs['Content-Type'], 'application/pdf')

        with patch('accounting.views.create_income_statement_pdf', return_value=BytesIO(b'%PDF')):
            inc = self.client.get(
                '/api/accounting/reports/income_statement/',
                {
                    'date_from': date.today().isoformat(),
                    'date_to': date.today().isoformat(),
                    'format': 'pdf',
                },
            )
            self.assertEqual(inc.status_code, status.HTTP_200_OK)

        with patch('accounting.views.create_trial_balance_pdf', return_value=BytesIO(b'%PDF')):
            tb = self.client.get(
                '/api/accounting/reports/trial_balance/',
                {'date': date.today().isoformat(), 'format': 'pdf'},
            )
            self.assertEqual(tb.status_code, status.HTTP_200_OK)

        missing = self.client.get(
            '/api/accounting/reports/general_ledger/',
            {'account_id': 999999},
        )
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)

        ledger = self.client.get(
            '/api/accounting/reports/general_ledger/',
            {
                'account_id': ap.id,
                'date_from': date.today().isoformat(),
                'date_to': date.today().isoformat(),
            },
        )
        self.assertEqual(ledger.status_code, status.HTTP_200_OK)

        stmt_missing = self.client.get(
            '/api/accounting/reports/account_statement/',
            {'account_id': 999999},
        )
        self.assertEqual(stmt_missing.status_code, status.HTTP_404_NOT_FOUND)

        stmt = self.client.get(
            '/api/accounting/reports/account_statement/',
            {
                'account_id': equity_acct.id,
                'date_from': date.today().isoformat(),
                'date_to': date.today().isoformat(),
            },
        )
        self.assertEqual(stmt.status_code, status.HTTP_200_OK)

        cash_flow = self.client.get(
            '/api/accounting/reports/cash_flow/',
            {
                'date_from': date.today().isoformat(),
                'date_to': date.today().isoformat(),
            },
        )
        self.assertEqual(cash_flow.status_code, status.HTTP_200_OK)

        # reverse requires accounting.correct — manager is denied
        txn = Transaction.objects.create(
            transaction_date=date.today(),
            description='Empty',
            created_by=user,
        )
        bad_reverse = self.client.post(
            f'/api/accounting/transactions/{txn.id}/reverse/',
            {},
            format='json',
        )
        self.assertEqual(bad_reverse.status_code, status.HTTP_403_FORBIDDEN)
