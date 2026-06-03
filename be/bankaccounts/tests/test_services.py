"""Bank account service layer tests."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from bankaccounts.models import BankAccount
from bankaccounts.services import BankAccountService, BankTransactionService


class BankAccountServiceTests(TestCase):
    def setUp(self):
        self.service = BankAccountService()
        self.user = User.objects.create_user('bank_tester', password='pass')

    def test_build_queryset_filters_active(self):
        BankAccount.objects.create(
            bank_name='KCB',
            account_name='Main',
            account_number='001',
            opening_balance=Decimal('1000'),
            current_balance=Decimal('1000'),
            is_active=True,
            created_by=self.user,
        )
        BankAccount.objects.create(
            bank_name='Equity',
            account_name='Old',
            account_number='002',
            opening_balance=Decimal('0'),
            current_balance=Decimal('0'),
            is_active=False,
            created_by=self.user,
        )
        active = list(self.service.build_queryset({'is_active': 'true'}))
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].bank_name, 'KCB')

    def test_build_queryset_without_filters_returns_all(self):
        BankAccount.objects.create(
            bank_name='A',
            account_name='A1',
            account_number='1',
            opening_balance=Decimal('0'),
            current_balance=Decimal('0'),
            created_by=self.user,
        )
        self.assertEqual(self.service.build_queryset().count(), 1)

    def test_update_balance_recomputes_from_transactions(self):
        account = BankAccount.objects.create(
            bank_name='KCB',
            account_name='Ops',
            account_number='010',
            opening_balance=Decimal('100'),
            current_balance=Decimal('100'),
            created_by=self.user,
        )
        from django.utils import timezone
        from bankaccounts.models import BankTransaction

        BankTransaction.objects.create(
            bank_account=account,
            transaction_type='deposit',
            amount=Decimal('50'),
            transaction_date=timezone.now().date(),
            description='Top-up',
            created_by=self.user,
        )
        updated = self.service.update_balance(account)
        self.assertEqual(updated.current_balance, Decimal('150'))


class BankTransactionServiceTests(TestCase):
    def setUp(self):
        self.service = BankTransactionService()
        self.user = User.objects.create_user('txn_user', password='pass')
        self.account = BankAccount.objects.create(
            bank_name='Equity',
            account_name='Main',
            account_number='TX-1',
            opening_balance=Decimal('0'),
            current_balance=Decimal('0'),
            created_by=self.user,
        )

    def test_build_queryset_invalid_account_returns_empty(self):
        qs = self.service.build_queryset({'account': 'not-a-number'})
        self.assertEqual(qs.count(), 0)

    def test_build_queryset_filters_by_account_and_dates(self):
        from django.utils import timezone
        from bankaccounts.models import BankTransaction

        today = timezone.now().date()
        BankTransaction.objects.create(
            bank_account=self.account,
            transaction_type='deposit',
            amount=Decimal('25'),
            transaction_date=today,
            description='In',
            created_by=self.user,
        )
        qs = self.service.build_queryset({
            'account': self.account.id,
            'date_from': today.isoformat(),
            'date_to': today.isoformat(),
        })
        self.assertEqual(qs.count(), 1)
