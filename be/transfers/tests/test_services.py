"""Money transfer service tests."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from bankaccounts.models import BankAccount
from transfers.models import MoneyTransfer
from transfers.services import MoneyTransferService


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
