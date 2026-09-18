"""Debt Management API — summary, debtors list, badge count."""

from decimal import Decimal
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status

from accounts.models import Permission
from sales.models import Customer, CustomerWalletTransaction
from sales.debt_management import (
    aging_bucket_for_days,
    build_debt_summary,
    debt_amount_from_balance,
    list_debtors,
)
from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase


def _seed_wallet_visible():
    cache.clear()
    ModuleSetting.objects.update_or_create(
        module='customers',
        key='show_wallet_balance',
        defaults={
            'label': 'show_wallet_balance',
            'description': '',
            'default_value': True,
            'value': True,
        },
    )


class DebtManagementUnitTests(ManagerAPITestCase):
    def test_aging_bucket_boundaries(self):
        self.assertEqual(aging_bucket_for_days(0), '0_7')
        self.assertEqual(aging_bucket_for_days(7), '0_7')
        self.assertEqual(aging_bucket_for_days(8), '8_30')
        self.assertEqual(aging_bucket_for_days(31), '31_60')
        self.assertEqual(aging_bucket_for_days(61), '60_plus')

    def test_debt_amount_from_balance(self):
        self.assertEqual(debt_amount_from_balance(Decimal('-40')), Decimal('40'))
        self.assertEqual(debt_amount_from_balance(Decimal('10')), Decimal('0'))


class DebtManagementAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_wallet_visible()
        self.debtor = Customer.objects.create(
            name='Owed Customer',
            phone='0700111000',
            wallet_balance=Decimal('-200.00'),
            is_active=True,
        )
        self.credit_customer = Customer.objects.create(
            name='Credit Customer',
            phone='0700222000',
            wallet_balance=Decimal('50.00'),
            is_active=True,
        )
        txn = CustomerWalletTransaction.objects.create(
            customer=self.debtor,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('200.00'),
            balance_after=Decimal('-200.00'),
            notes='Pay later',
        )
        CustomerWalletTransaction.objects.filter(pk=txn.pk).update(
            created_at=timezone.now() - timedelta(days=10),
        )

    def test_debt_summary_includes_debtor(self):
        response = self.client.get('/api/sales/customers/debt-summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['customers_with_debt'], 1)
        self.assertEqual(Decimal(response.data['total_debt']), Decimal('200.00'))
        self.assertEqual(response.data['aging']['8_30']['count'], 1)

    def test_debtors_list_excludes_credit_balances(self):
        response = self.client.get('/api/sales/customers/debtors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['count'], 1)
        row = response.data['results'][0]
        self.assertEqual(row['id'], self.debtor.id)
        self.assertEqual(Decimal(row['debt_amount']), Decimal('200.00'))
        self.assertEqual(row['aging_bucket'], '8_30')

    def test_debtor_count(self):
        response = self.client.get('/api/sales/customers/debtor-count/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_customer_view_permission_does_not_grant_debt_management(self):
        self.manager_role.permissions.remove(
            Permission.objects.get(module='debt_management', action='view')
        )
        self.assertTrue(
            self.manager_role.permissions.filter(module='customers', action='view').exists()
        )

        response = self.client.get('/api/sales/customers/debt-summary/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('debt_management.view', str(response.data))

    def test_debt_summary_forbidden_when_wallet_hidden(self):
        SettingsService.set('customers', 'show_wallet_balance', False)
        response = self.client.get('/api/sales/customers/debt-summary/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_debtors_filter_by_bucket(self):
        results, count = list_debtors(aging_bucket='0_7')
        self.assertEqual(count, 0)
        results, count = list_debtors(aging_bucket='8_30')
        self.assertEqual(count, 1)

    def test_build_debt_summary_collected_today(self):
        CustomerWalletTransaction.objects.create(
            customer=self.debtor,
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('25.00'),
            balance_after=Decimal('-175.00'),
        )
        summary = build_debt_summary()
        self.assertEqual(summary['collected_today'], Decimal('25.00'))

    def test_list_debt_collections_for_a_day(self):
        from sales.debt_management import list_debt_collections

        today_pay = CustomerWalletTransaction.objects.create(
            customer=self.debtor,
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('40.00'),
            balance_after=Decimal('-160.00'),
            notes='Cash at counter',
            created_by=self.manager_user,
        )
        old_pay = CustomerWalletTransaction.objects.create(
            customer=self.debtor,
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('10.00'),
            balance_after=Decimal('-190.00'),
        )
        CustomerWalletTransaction.objects.filter(pk=old_pay.pk).update(
            created_at=timezone.now() - timedelta(days=2),
        )

        payload = list_debt_collections()
        self.assertEqual(payload['count'], 1)
        self.assertEqual(Decimal(payload['total']), Decimal('40.00'))
        row = payload['results'][0]
        self.assertEqual(row['id'], today_pay.id)
        self.assertEqual(row['customer_name'], 'Owed Customer')
        self.assertEqual(Decimal(row['amount']), Decimal('40.00'))
        self.assertEqual(row['received_by'], self.manager_user.username)

    def test_debt_collections_api(self):
        CustomerWalletTransaction.objects.create(
            customer=self.debtor,
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('15.50'),
            balance_after=Decimal('-184.50'),
            created_by=self.manager_user,
        )
        today = timezone.localdate().isoformat()
        response = self.client.get(
            '/api/sales/customers/debt-collections/',
            {'date': today},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(Decimal(response.data['total']), Decimal('15.50'))
        self.assertEqual(response.data['results'][0]['customer_name'], 'Owed Customer')

    def test_debt_collections_rejects_bad_date(self):
        response = self.client.get(
            '/api/sales/customers/debt-collections/',
            {'date': 'not-a-date'},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
