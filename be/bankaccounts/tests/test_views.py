"""Bank account API coverage."""

from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from bankaccounts.models import BankAccount, BankTransaction
from utils.tests.api_test_base import ManagerAPITestCase


class BankAccountViewsTests(ManagerAPITestCase):
    def test_list_filter_and_update_balance(self):
        account = BankAccount.objects.create(
            account_name='Till',
            account_number='TILL-1',
            bank_name='Equity',
            opening_balance=Decimal('100.00'),
            current_balance=Decimal('100.00'),
            is_active=True,
            created_by=self.manager_user,
        )
        listed = self.client.get('/api/bank-accounts/accounts/', {'is_active': 'true'})
        self.assertEqual(listed.status_code, status.HTTP_200_OK)

        BankTransaction.objects.create(
            bank_account=account,
            transaction_type='deposit',
            amount=Decimal('25.00'),
            transaction_date=timezone.localdate(),
            description='Float top-up',
            created_by=self.manager_user,
        )
        bal = self.client.post(f'/api/bank-accounts/accounts/{account.id}/update_balance/')
        self.assertEqual(bal.status_code, status.HTTP_200_OK, bal.data)

        txns = self.client.get(
            '/api/bank-accounts/transactions/',
            {
                'account': account.id,
                'date_from': timezone.localdate().isoformat(),
                'date_to': timezone.localdate().isoformat(),
            },
        )
        self.assertEqual(txns.status_code, status.HTTP_200_OK)
