"""Money transfer API tests."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SUPER_ADMIN, sync_default_roles
from bankaccounts.models import BankAccount
from transfers.models import MoneyTransfer
from utils.tests.api_test_base import ManagerAPITestCase


class TransferViewsTestCase(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.from_acct = BankAccount.objects.create(
            account_name='HQ Account',
            account_number='HQ-001',
            bank_name='KCB',
            created_by=cls.manager_user,
        )
        cls.to_acct = BankAccount.objects.create(
            account_name='Branch Float',
            account_number='HQ-002',
            bank_name='KCB',
            created_by=cls.manager_user,
        )

    def test_create_and_approve_transfer(self):
        create = self.client.post(
            '/api/transfers/',
            {
                'transfer_type': 'bank_to_bank',
                'from_account': self.from_acct.id,
                'to_account': self.to_acct.id,
                'amount': '250.00',
                'transfer_date': timezone.now().date().isoformat(),
                'description': 'Branch float',
                'status': 'pending',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        sync_default_roles()
        checker = User.objects.create_user('xfer_view_chk', password='x', is_staff=True)
        UserProfile.objects.create(
            user=checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        approve = client.post(f'/api/transfers/{create.data["id"]}/approve/')
        self.assertEqual(approve.status_code, status.HTTP_200_OK)
        self.assertEqual(approve.data['status'], 'completed')

    def test_statistics(self):
        MoneyTransfer.objects.create(
            transfer_type='bank_to_bank',
            from_account=self.from_acct,
            to_account=self.to_acct,
            amount=Decimal('100'),
            transfer_date=timezone.now().date(),
            status='completed',
            description='Done',
            created_by=self.manager_user,
        )
        response = self.client.get('/api/transfers/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
