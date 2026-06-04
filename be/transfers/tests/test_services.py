"""Money transfer service tests."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.test import TestCase
from django.utils import timezone

from bankaccounts.models import BankAccount
from transfers.models import MoneyTransfer
from transfers.services import MoneyTransferService
from settings.models import StoreSettings


class MoneyTransferServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='xfer', password='x')
        self.from_acct = BankAccount.objects.create(
            account_name='Main',
            account_number='ACC-001',
            bank_name='Test Bank',
            opening_balance=Decimal('10000'),
            current_balance=Decimal('10000'),
            created_by=self.user,
        )
        self.to_acct = BankAccount.objects.create(
            account_name='Petty Cash',
            account_number='ACC-002',
            bank_name='Test Bank',
            opening_balance=Decimal('0'),
            current_balance=Decimal('0'),
            created_by=self.user,
        )
        self.service = MoneyTransferService()

    def test_approve_transfer(self):
        transfer = MoneyTransfer.objects.create(
            transfer_type='bank_to_bank',
            from_account=self.from_acct,
            to_account=self.to_acct,
            amount=Decimal('500.00'),
            transfer_date=timezone.now().date(),
            status='pending',
            description='Float top-up',
            created_by=self.user,
        )
        done = self.service.approve_transfer(transfer, self.user)
        self.assertEqual(done.status, 'completed')

    def test_maker_checker_blocks_self_approve(self):
        store = StoreSettings.load()
        store.maker_checker_enabled = True
        store.save(update_fields=['maker_checker_enabled'])
        transfer = MoneyTransfer.objects.create(
            transfer_type='bank_to_bank',
            from_account=self.from_acct,
            to_account=self.to_acct,
            amount=Decimal('200.00'),
            transfer_date=timezone.now().date(),
            status='pending',
            description='MC transfer',
            created_by=self.user,
        )
        checker = User.objects.create_user(username='checker_xfer', password='x')
        with self.assertRaises(DRFValidationError):
            self.service.approve_transfer(transfer, self.user)
        done = self.service.approve_transfer(transfer, checker)
        self.assertEqual(done.status, 'completed')
        store.maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled'])

    def test_approve_completed_raises(self):
        transfer = MoneyTransfer.objects.create(
            transfer_type='bank_to_bank',
            from_account=self.from_acct,
            to_account=self.to_acct,
            amount=Decimal('100.00'),
            transfer_date=timezone.now().date(),
            status='completed',
            description='Done',
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            self.service.approve_transfer(transfer, self.user)

    def test_build_queryset_without_filters_returns_ordered(self):
        MoneyTransfer.objects.create(
            transfer_type='bank_to_bank',
            from_account=self.from_acct,
            to_account=self.to_acct,
            amount=Decimal('1.00'),
            transfer_date=timezone.now().date(),
            status='pending',
            description='Listed',
            created_by=self.user,
        )
        self.assertEqual(self.service.build_queryset().count(), 1)

    def test_build_queryset_filters(self):
        pending = MoneyTransfer.objects.create(
            transfer_type='bank_to_bank',
            from_account=self.from_acct,
            to_account=self.to_acct,
            amount=Decimal('250.00'),
            transfer_date=timezone.now().date(),
            status='pending',
            description='Pending xfer',
            created_by=self.user,
        )
        self.service.approve_transfer(pending, self.user)
        qs = self.service.build_queryset({
            'status': 'completed',
            'transfer_type': 'bank_to_bank',
            'account': self.from_acct.id,
        })
        self.assertEqual(qs.count(), 1)

    def test_build_queryset_invalid_account_returns_empty(self):
        qs = self.service.build_queryset({'account': 'nope'})
        self.assertEqual(qs.count(), 0)

    def test_build_queryset_date_filters(self):
        today = timezone.now().date()
        MoneyTransfer.objects.create(
            transfer_type='bank_to_bank',
            from_account=self.from_acct,
            to_account=self.to_acct,
            amount=Decimal('10.00'),
            transfer_date=today,
            status='pending',
            description='Dated',
            created_by=self.user,
        )
        qs = self.service.build_queryset({
            'date_from': today,
            'date_to': today,
        })
        self.assertEqual(qs.count(), 1)

    def test_get_transfer_statistics(self):
        self.service.approve_transfer(
            MoneyTransfer.objects.create(
                transfer_type='bank_to_bank',
                from_account=self.from_acct,
                to_account=self.to_acct,
                amount=Decimal('50.00'),
                transfer_date=timezone.now().date(),
                status='pending',
                description='Stats',
                created_by=self.user,
            ),
            self.user,
        )
        stats = self.service.get_transfer_statistics()
        self.assertGreaterEqual(stats['total_transferred'], 50.0)
        self.assertTrue(any(row['status'] == 'completed' for row in stats['by_status']))
