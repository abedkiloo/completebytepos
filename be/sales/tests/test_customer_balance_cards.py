"""Customer summary cards filter the list by wallet debt or invoice balance."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import (
    ROLE_FIELD_AGENT,
    ROLE_PAYROLL_ADMIN,
    ensure_permissions,
    sync_default_roles,
)
from sales.customer_balance import normalize_balance_filter
from sales.models import Customer, Invoice
from settings.settings_service import SettingsService
from utils.tests.api_test_base import SuperAdminAPITestCase


class BalanceFilterUnitTests(SimpleTestCase):
    """The query value is ignored unless that balance is visible."""

    def test_unknown_and_hidden_filters_are_blank(self):
        self.assertEqual(normalize_balance_filter(''), '')
        self.assertEqual(normalize_balance_filter('everything'), '')
        self.assertEqual(normalize_balance_filter('x' * 40), '')
        self.assertEqual(
            normalize_balance_filter('wallet_debt', wallet_visible=False),
            '',
        )
        self.assertEqual(
            normalize_balance_filter('invoice', invoice_visible=False),
            '',
        )
        self.assertEqual(normalize_balance_filter('wallet_debt'), 'wallet_debt')
        self.assertEqual(normalize_balance_filter('wallet_credit'), 'wallet_credit')
        self.assertEqual(
            normalize_balance_filter('wallet_credit', wallet_visible=False),
            '',
        )
        self.assertEqual(normalize_balance_filter('invoice'), 'invoice')


class CustomerBalanceCardTests(SuperAdminAPITestCase):
    """Clicking a card is ``?balance=`` and the totals stay store-wide."""

    def setUp(self):
        super().setUp()
        self.debtor = Customer.objects.create(
            name='Wallet Debtor',
            phone='0718001111',
            wallet_balance=Decimal('-14900.00'),
        )
        self.clear = Customer.objects.create(
            name='Clear Shop',
            phone='0718002222',
            wallet_balance=Decimal('25.00'),
        )
        self.invoiced = Customer.objects.create(
            name='Invoice Shop',
            phone='0718003333',
            wallet_balance=Decimal('0.00'),
        )
        Invoice.objects.create(
            customer=self.invoiced,
            subtotal=Decimal('80.00'),
            total=Decimal('80.00'),
            amount_paid=Decimal('0.00'),
            issued_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=7),
            status='sent',
            created_by=self.admin,
        )

    def test_wallet_card_lists_only_debtors_and_keeps_the_full_total(self):
        response = self.client.get('/api/sales/customers/', {'balance': 'wallet_debt'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row['name'] for row in response.data['results']]
        self.assertEqual(names, ['Wallet Debtor'])
        summary = response.data['balance_summary']
        self.assertEqual(summary['count'], 3)
        self.assertEqual(summary['with_wallet_debt'], 1)
        self.assertEqual(summary['total_wallet_debt'], '14900.00')
        self.assertEqual(summary['with_invoice'], 1)
        self.assertEqual(summary['invoice_outstanding'], '80.00')
        self.assertEqual(summary['with_wallet_credit'], 1)
        self.assertEqual(summary['total_wallet_credit'], '25.00')

    def test_credit_card_lists_customers_whose_money_we_hold(self):
        response = self.client.get('/api/sales/customers/', {'balance': 'wallet_credit'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row['name'] for row in response.data['results']]
        self.assertEqual(names, ['Clear Shop'])
        self.assertEqual(response.data['balance_summary']['with_wallet_credit'], 1)
        self.assertEqual(response.data['balance_summary']['total_wallet_credit'], '25.00')
        self.assertEqual(response.data['balance_summary']['with_wallet_debt'], 1)

    def test_invoice_card_lists_only_open_invoices(self):
        response = self.client.get('/api/sales/customers/', {'balance': 'invoice'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row['name'] for row in response.data['results']]
        self.assertEqual(names, ['Invoice Shop'])
        self.assertEqual(response.data['balance_summary']['with_invoice'], 1)

    def test_hidden_wallet_ignores_the_filter_and_zeroes_the_total(self):
        SettingsService.set('customers', 'show_wallet_balance', False)
        try:
            response = self.client.get('/api/sales/customers/', {'balance': 'wallet_debt'})
        finally:
            SettingsService.set('customers', 'show_wallet_balance', True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {row['name'] for row in response.data['results']}
        self.assertIn('Clear Shop', names)
        self.assertEqual(response.data['balance_summary']['with_wallet_debt'], 0)
        self.assertEqual(response.data['balance_summary']['total_wallet_debt'], '0.00')
        self.assertEqual(response.data['balance_summary']['with_wallet_credit'], 0)
        self.assertEqual(response.data['balance_summary']['total_wallet_credit'], '0.00')
        self.assertNotIn('14900.00', str(response.data['balance_summary']))
        self.assertNotIn('25.00', str(response.data['balance_summary']))

    def test_three_hundred_customers_still_count_the_one_debtor(self):
        Customer.objects.bulk_create([
            Customer(
                name=f'Bulk {index:03d}',
                customer_code=f'BAL-{index:06d}',
                phone=f'0722{index:06d}',
                wallet_balance=Decimal('0.00'),
                is_active=True,
            )
            for index in range(300)
        ])
        started = timezone.now()
        response = self.client.get('/api/sales/customers/', {'balance': 'wallet_debt', 'page_size': 50})
        elapsed = timezone.now() - started
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['balance_summary']['count'], 303)
        self.assertEqual(response.data['balance_summary']['with_wallet_debt'], 1)
        self.assertEqual(response.data['results'][0]['name'], 'Wallet Debtor')
        self.assertLess(elapsed.total_seconds(), 5)


class CustomerBalanceSecurityTests(SuperAdminAPITestCase):
    """The filter uses the same customer list permission and visibility."""

    def test_anonymous_cannot_read_the_debt_filter(self):
        Customer.objects.create(
            name='Hidden Debt',
            phone='0718999000',
            wallet_balance=Decimal('-14900.00'),
        )
        response = APIClient().get('/api/sales/customers/', {'balance': 'wallet_debt'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('14900', response.content.decode())
        self.assertNotIn('0718999000', response.content.decode())

    def test_payroll_admin_cannot_open_the_filtered_list(self):
        ensure_permissions()
        sync_default_roles()
        payroll = User.objects.create_user(username='balance_payroll', password='x')
        UserProfile.objects.create(
            user=payroll,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_PAYROLL_ADMIN),
            is_active=True,
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(payroll).access_token}')
        response = client.get('/api/sales/customers/', {'balance': 'wallet_debt'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn('wallet_balance', response.content.decode())

    def test_field_sales_summary_excludes_another_agents_debt(self):
        ensure_permissions()
        sync_default_roles()
        agent = User.objects.create_user(username='balance_agent', password='x')
        UserProfile.objects.create(
            user=agent,
            role='field_agent',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
            is_active=True,
        )
        Customer.objects.create(
            name='Own Duka',
            phone='0718004444',
            wallet_balance=Decimal('-100.00'),
            created_by=agent,
        )
        Customer.objects.create(
            name='Other Duka',
            phone='0718005555',
            wallet_balance=Decimal('-9999.50'),
            created_by=self.admin,
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(agent).access_token}')
        response = client.get('/api/sales/customers/', {'balance': 'wallet_debt'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row['name'] for row in response.data['results']]
        self.assertEqual(names, ['Own Duka'])
        self.assertEqual(response.data['balance_summary']['total_wallet_debt'], '100.00')
        self.assertNotIn('9999.50', response.content.decode())
        self.assertNotIn('0718005555', response.content.decode())
