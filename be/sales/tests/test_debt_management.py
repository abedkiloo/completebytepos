"""Debt Management API — summary, debtors list, badge count."""

from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import ROLE_SALES
from sales.models import Customer, CustomerWalletTransaction, Sale
from sales.debt_management import (
    aging_bucket_for_days,
    build_debt_summary,
    debt_amount_from_balance,
    list_debtors,
)
from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


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
            payment_method='cash',
            reference='',
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
        self.assertEqual(row['payment_method'], 'cash')
        self.assertEqual(row['payment_method_label'], 'Cash')
        self.assertEqual(row['reference'], '')

    def test_list_debt_collections_infers_mpesa_from_legacy_notes(self):
        from sales.debt_management import list_debt_collections

        CustomerWalletTransaction.objects.create(
            customer=self.debtor,
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('50.00'),
            balance_after=Decimal('-150.00'),
            reference='QHX7K2L9M1',
            notes='Debt payment received via M-PESA (ref: QHX7K2L9M1)',
            created_by=self.manager_user,
        )
        row = list_debt_collections()['results'][0]
        self.assertEqual(row['payment_method'], 'mpesa')
        self.assertEqual(row['payment_method_label'], 'M-PESA')
        self.assertEqual(row['reference'], 'QHX7K2L9M1')

    def test_debt_collections_api(self):
        CustomerWalletTransaction.objects.create(
            customer=self.debtor,
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('15.50'),
            balance_after=Decimal('-184.50'),
            payment_method='mpesa',
            reference='ABC12345',
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

    def test_manager_sees_other_cashier_debtors(self):
        other_user = User.objects.create_user('debt_other_cashier', password='x')
        other_customer = Customer.objects.create(
            name='Other Cashier Debtor',
            phone='0700333000',
            wallet_balance=Decimal('-80.00'),
            is_active=True,
        )
        sale = Sale.objects.create(
            cashier=other_user,
            customer=other_customer,
            subtotal=Decimal('80.00'),
            total=Decimal('80.00'),
            amount_paid=Decimal('0.00'),
            status='completed',
            payment_method='other',
        )
        CustomerWalletTransaction.objects.create(
            customer=other_customer,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('80.00'),
            balance_after=Decimal('-80.00'),
            sale=sale,
            created_by=other_user,
        )

        response = self.client.get('/api/sales/customers/debtors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        ids = {row['id'] for row in response.data['results']}
        self.assertIn(self.debtor.id, ids)
        self.assertIn(other_customer.id, ids)
        self.assertEqual(response.data['count'], 2)

    def test_unpaid_sale_without_wallet_debt_appears_on_debtors_list(self):
        """Profile order debt must surface on Debt Management so staff can collect."""
        stuck = Customer.objects.create(
            name='Stuck Unpaid Sale',
            phone='0700444000',
            wallet_balance=Decimal('0.00'),
            is_active=True,
        )
        Sale.objects.create(
            cashier=self.manager_user,
            customer=stuck,
            subtotal=Decimal('500.00'),
            total=Decimal('500.00'),
            amount_paid=Decimal('100.00'),
            status='completed',
            sale_type='pos',
            payment_method='cash',
        )

        response = self.client.get('/api/sales/customers/debtors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        ids = {row['id'] for row in response.data['results']}
        self.assertIn(stuck.id, ids)
        row = next(r for r in response.data['results'] if r['id'] == stuck.id)
        self.assertEqual(Decimal(row['debt_amount']), Decimal('400.00'))
        # List GET stays read-only/fast; wallet is synced on profile or receive payment.
        stuck.refresh_from_db()
        self.assertEqual(stuck.wallet_balance, Decimal('0.00'))

    def test_inactive_customer_with_debt_still_listed(self):
        self.debtor.is_active = False
        self.debtor.save(update_fields=['is_active'])

        response = self.client.get('/api/sales/customers/debtors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        ids = {row['id'] for row in response.data['results']}
        self.assertIn(self.debtor.id, ids)


def _create_sale_debt(user, customer, amount, *, served_by=None, created_by=None):
    sale = Sale.objects.create(
        cashier=user,
        served_by=served_by,
        customer=customer,
        subtotal=amount,
        total=amount,
        amount_paid=Decimal('0.00'),
        status='completed',
        payment_method='other',
    )
    CustomerWalletTransaction.objects.create(
        customer=customer,
        transaction_type='debit',
        source_type='debt',
        amount=amount,
        balance_after=customer.wallet_balance,
        sale=sale,
        created_by=created_by or user,
    )
    return sale


class SalesDebtVisibilityAPITests(SalesAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_wallet_visible()
        self.other_sales = User.objects.create_user('debt_sales_b', password='x')
        UserProfile.objects.create(
            user=self.other_sales,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        self.my_customer = Customer.objects.create(
            name='My Credit Sale',
            phone='0710111000',
            wallet_balance=Decimal('-200.00'),
            is_active=True,
        )
        self.other_customer = Customer.objects.create(
            name='Other Credit Sale',
            phone='0710222000',
            wallet_balance=Decimal('-90.00'),
            is_active=True,
        )
        _create_sale_debt(self.sales_user, self.my_customer, Decimal('200.00'))
        _create_sale_debt(self.other_sales, self.other_customer, Decimal('90.00'))

    def test_salesperson_who_can_collect_sees_all_debtors(self):
        """Collectors need the full board — profiles already show every customer's debt."""
        response = self.client.get('/api/sales/customers/debtors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        ids = {row['id'] for row in response.data['results']}
        self.assertEqual(ids, {self.my_customer.id, self.other_customer.id})
        self.assertEqual(response.data['count'], 2)

        summary = self.client.get('/api/sales/customers/debt-summary/')
        self.assertEqual(summary.status_code, status.HTTP_200_OK, summary.data)
        self.assertEqual(summary.data['customers_with_debt'], 2)
        self.assertEqual(Decimal(summary.data['total_debt']), Decimal('290.00'))

        count = self.client.get('/api/sales/customers/debtor-count/')
        self.assertEqual(count.status_code, status.HTTP_200_OK)
        self.assertEqual(count.data['count'], 2)

    def test_salesperson_view_only_still_limited_to_own_debtors(self):
        from accounts.models import Permission

        self.sales_user.profile.custom_role.permissions.remove(
            Permission.objects.get(module='debt_management', action='update')
        )
        response = self.client.get('/api/sales/customers/debtors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        ids = {row['id'] for row in response.data['results']}
        self.assertEqual(ids, {self.my_customer.id})

    def test_salesperson_still_sees_customer_after_someone_else_collects(self):
        CustomerWalletTransaction.objects.create(
            customer=self.my_customer,
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('50.00'),
            balance_after=Decimal('-150.00'),
            created_by=self.other_sales,
        )
        self.my_customer.wallet_balance = Decimal('-150.00')
        self.my_customer.save(update_fields=['wallet_balance'])

        CustomerWalletTransaction.objects.create(
            customer=self.other_customer,
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('20.00'),
            balance_after=Decimal('-70.00'),
            created_by=self.other_sales,
        )
        self.other_customer.wallet_balance = Decimal('-70.00')
        self.other_customer.save(update_fields=['wallet_balance'])

        response = self.client.get('/api/sales/customers/debtors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        ids = {row['id'] for row in response.data['results']}
        self.assertEqual(ids, {self.my_customer.id, self.other_customer.id})
        mine = next(r for r in response.data['results'] if r['id'] == self.my_customer.id)
        self.assertEqual(Decimal(mine['debt_amount']), Decimal('150.00'))

        collections = self.client.get('/api/sales/customers/debt-collections/')
        self.assertEqual(collections.status_code, status.HTTP_200_OK, collections.data)
        # Full board: both settlements today are visible to collectors.
        self.assertEqual(collections.data['count'], 2)

        summary = self.client.get('/api/sales/customers/debt-summary/')
        self.assertEqual(Decimal(summary.data['collected_today']), Decimal('70.00'))

    def test_served_by_salesperson_sees_the_debt(self):
        served_customer = Customer.objects.create(
            name='Served Credit Sale',
            phone='0710333000',
            wallet_balance=Decimal('-40.00'),
            is_active=True,
        )
        _create_sale_debt(
            self.other_sales,
            served_customer,
            Decimal('40.00'),
            served_by=self.sales_user,
            created_by=self.other_sales,
        )

        response = self.client.get('/api/sales/customers/debtors/')
        ids = {row['id'] for row in response.data['results']}
        self.assertIn(self.my_customer.id, ids)
        self.assertIn(served_customer.id, ids)
        self.assertIn(self.other_customer.id, ids)
