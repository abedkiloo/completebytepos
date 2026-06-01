"""Extended money transfer queryset, statistics, and API coverage."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from bankaccounts.models import BankAccount
from settings.models import ModuleSettings
from transfers.models import MoneyTransfer
from transfers.services import MoneyTransferService
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class TransferQuerysetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='xfer_qs', password='x')
        self.from_acct = BankAccount.objects.create(
            account_name='Main',
            account_number='X-001',
            bank_name='Bank',
            created_by=self.user,
        )
        self.to_acct = BankAccount.objects.create(
            account_name='Petty',
            account_number='X-002',
            bank_name='Bank',
            created_by=self.user,
        )
        self.service = MoneyTransferService()
        today = timezone.now().date()
        MoneyTransfer.objects.create(
            transfer_type='bank_to_bank',
            from_account=self.from_acct,
            to_account=self.to_acct,
            amount=Decimal('100.00'),
            transfer_date=today,
            status='pending',
            description='Pending',
            created_by=self.user,
        )
        MoneyTransfer.objects.create(
            transfer_type='bank_to_bank',
            from_account=self.from_acct,
            to_account=self.to_acct,
            amount=Decimal('250.00'),
            transfer_date=today,
            status='completed',
            description='Done',
            created_by=self.user,
        )

    def test_build_queryset_status_filter(self):
        qs = self.service.build_queryset({'status': 'completed'})
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().amount, Decimal('250.00'))

    def test_build_queryset_account_filter_matches_either_side(self):
        qs = self.service.build_queryset({'account': str(self.to_acct.id)})
        self.assertEqual(qs.count(), 2)

    def test_statistics_completed_only_in_total(self):
        stats = self.service.get_transfer_statistics()
        self.assertEqual(stats['total_transferred'], 250.0)
        self.assertTrue(any(row['transfer_type'] == 'bank_to_bank' for row in stats['by_type']))


class TransferAPIExtendedTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.from_acct = BankAccount.objects.create(
            account_name='HQ',
            account_number='HQ-100',
            bank_name='KCB',
            created_by=cls.manager_user,
        )
        cls.to_acct = BankAccount.objects.create(
            account_name='Branch',
            account_number='HQ-101',
            bank_name='KCB',
            created_by=cls.manager_user,
        )

    def test_list_filter_by_status(self):
        MoneyTransfer.objects.create(
            transfer_type='bank_to_bank',
            from_account=self.from_acct,
            to_account=self.to_acct,
            amount=Decimal('50.00'),
            transfer_date=timezone.now().date(),
            status='pending',
            description='Wait',
            created_by=self.manager_user,
        )
        response = self.client.get('/api/transfers/?status=completed')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', response.data)
        for row in rows:
            self.assertEqual(row['status'], 'completed')

    def test_double_approve_returns_400(self):
        create = self.client.post(
            '/api/transfers/',
            {
                'transfer_type': 'bank_to_bank',
                'from_account': self.from_acct.id,
                'to_account': self.to_acct.id,
                'amount': '75.00',
                'transfer_date': timezone.now().date().isoformat(),
                'description': 'Once',
                'status': 'pending',
            },
            format='json',
        )
        transfer_id = create.data['id']
        self.client.post(f'/api/transfers/{transfer_id}/approve/')
        again = self.client.post(f'/api/transfers/{transfer_id}/approve/')
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)


class TransferPermissionsTestCase(SalesAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ModuleSettings.objects.update_or_create(
            module_name='money_transfer',
            defaults={'description': 'money_transfer', 'is_enabled': True},
        )

    def test_sales_cannot_create_transfer(self):
        response = self.client.post(
            '/api/transfers/',
            {
                'transfer_type': 'bank_to_bank',
                'amount': '10.00',
                'transfer_date': timezone.now().date().isoformat(),
                'description': 'Nope',
                'status': 'pending',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
