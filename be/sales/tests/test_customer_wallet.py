"""Customer wallet debt visibility and settlement API."""

from decimal import Decimal

from django.core.cache import cache
from rest_framework import status

from sales.models import Customer, CustomerWalletTransaction
from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase


def _seed_customer_settings():
    cache.clear()
    for key, default in (
        ('show_customer_code', True),
        ('show_outstanding_balance', True),
        ('show_wallet_balance', True),
        ('enable_customer_create', True),
        ('enable_customer_edit', True),
        ('enable_customer_delete', True),
        ('enable_wallet_payment', True),
        ('show_customer_type', True),
        ('show_tax_id', True),
        ('show_customer_notes', True),
        ('show_customer_status', True),
        ('allow_quick_add_at_pos', True),
    ):
        ModuleSetting.objects.update_or_create(
            module='customers',
            key=key,
            defaults={
                'label': key,
                'description': '',
                'default_value': default,
                'value': default,
            },
        )


class CustomerWalletAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_customer_settings()
        self.customer = Customer.objects.create(
            name='Debtor Customer',
            phone='0711222333',
            wallet_balance=Decimal('-250.00'),
            is_active=True,
        )

    def test_list_includes_wallet_balance(self):
        response = self.client.get('/api/sales/customers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', response.data)
        row = next(c for c in rows if c['id'] == self.customer.id)
        self.assertEqual(Decimal(row['wallet_balance']), Decimal('-250.00'))

    def test_wallet_transactions_lists_debt_entries(self):
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('250.00'),
            balance_after=Decimal('-250.00'),
            notes='Unpaid balance from sale',
        )
        response = self.client.get(
            f'/api/sales/customers/{self.customer.id}/wallet-transactions/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['source_type'], 'debt')
        self.assertEqual(response.data[0]['amount'], '250.00')

    def test_receive_wallet_payment_credits_wallet(self):
        response = self.client.post(
            f'/api/sales/customers/{self.customer.id}/receive-wallet-payment/',
            {
                'amount': '100.00',
                'payment_method': 'cash',
                'reference': 'RCPT-1',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(response.data['wallet_balance']), Decimal('-150.00'))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('-150.00'))
        txn = CustomerWalletTransaction.objects.filter(
            customer=self.customer, source_type='debt_settlement'
        ).first()
        self.assertIsNotNone(txn)
        self.assertEqual(txn.amount, Decimal('100.00'))

    def test_receive_wallet_payment_settles_full_debt(self):
        response = self.client.post(
            f'/api/sales/customers/{self.customer.id}/receive-wallet-payment/',
            {'amount': '250.00', 'payment_method': 'mpesa', 'reference': 'ABC123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('0.00'))

    def test_receive_wallet_payment_rejects_zero_amount(self):
        response = self.client.post(
            f'/api/sales/customers/{self.customer.id}/receive-wallet-payment/',
            {'amount': '0', 'payment_method': 'cash'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_receive_wallet_payment_forbidden_when_disabled(self):
        SettingsService.set('customers', 'enable_wallet_payment', False)
        response = self.client.post(
            f'/api/sales/customers/{self.customer.id}/receive-wallet-payment/',
            {'amount': '50.00', 'payment_method': 'cash'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_wallet_transactions_forbidden_when_wallet_hidden(self):
        SettingsService.set('customers', 'show_wallet_balance', False)
        response = self.client.get(
            f'/api/sales/customers/{self.customer.id}/wallet-transactions/'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
