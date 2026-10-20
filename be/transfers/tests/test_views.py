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

    def _admin_client(self):
        sync_default_roles()
        admin = User.objects.create_user('xfer_admin', password='x', is_staff=True)
        UserProfile.objects.create(
            user=admin,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(admin)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def test_reject_and_resubmit_transfer(self):
        create = self.client.post(
            '/api/transfers/',
            {
                'transfer_type': 'bank_to_bank',
                'from_account': self.from_acct.id,
                'to_account': self.to_acct.id,
                'amount': '80.00',
                'transfer_date': timezone.now().date().isoformat(),
                'description': 'Needs review',
                'status': 'pending',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        admin = self._admin_client()
        reject = admin.post(
            f'/api/transfers/{create.data["id"]}/reject/',
            {'rejection_reason': 'Wrong accounts'},
            format='json',
        )
        self.assertEqual(reject.status_code, status.HTTP_200_OK, reject.data)
        self.assertIn(reject.data['status'], ('rejected', 'cancelled'))

        # Maker resubmits via service (API update perm is role-gated separately).
        from transfers.services import MoneyTransferService

        transfer = MoneyTransfer.objects.get(pk=create.data['id'])
        queued = MoneyTransferService().resubmit_transfer(transfer, self.manager_user)
        self.assertEqual(queued.status, 'pending')

    def test_reject_requires_reason(self):
        transfer = MoneyTransfer.objects.create(
            transfer_type='bank_to_bank',
            from_account=self.from_acct,
            to_account=self.to_acct,
            amount=Decimal('40'),
            transfer_date=timezone.now().date(),
            status='pending',
            description='No reason',
            created_by=self.manager_user,
        )
        admin = self._admin_client()
        reject = admin.post(f'/api/transfers/{transfer.id}/reject/', {}, format='json')
        self.assertEqual(reject.status_code, status.HTTP_400_BAD_REQUEST)
