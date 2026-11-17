"""Payments trail — money-in list with paid-towards targets."""

from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from products.models import Category, Product
from sales.models import (
    Customer,
    CustomerWalletTransaction,
    DebtSettlementAllocation,
    Sale,
    SaleItem,
)
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES
from sales.payments_trail import list_payments_trail
from sales.services import CustomerService
from utils.tests.api_test_base import ManagerAPITestCase


class PaymentsTrailTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            name='Trail Customer',
            phone='0700111222',
            wallet_balance=Decimal('-500.00'),
            is_active=True,
        )
        category = Category.objects.create(name='Trail', is_active=True)
        self.product = Product.objects.create(
            name='Trail Item',
            sku='TRAIL-1',
            category=category,
            price=Decimal('500'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )
        self.sale = Sale.objects.create(
            sale_number='SALE-TRAIL-1',
            status='completed',
            sale_type='pos',
            customer=self.customer,
            subtotal=Decimal('500.00'),
            total=Decimal('500.00'),
            amount_paid=Decimal('0'),
            payment_method='cash',
            cashier=self.manager_user,
            occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('500'),
            subtotal=Decimal('500'),
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('500.00'),
            balance_after=Decimal('-500.00'),
            sale=self.sale,
            created_by=self.manager_user,
        )

    def test_settlement_creates_allocation_and_appears_on_trail(self):
        txn = CustomerService().record_wallet_payment(
            self.customer,
            Decimal('200.00'),
            payment_method='mpesa',
            reference='QHXTRAIL01',
            user=self.manager_user,
        )
        allocs = list(
            DebtSettlementAllocation.objects.filter(wallet_transaction=txn).select_related(
                'sale'
            )
        )
        self.assertEqual(len(allocs), 1)
        self.assertEqual(allocs[0].sale_id, self.sale.id)
        self.assertEqual(allocs[0].amount, Decimal('200.00'))
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.amount_paid, Decimal('200.00'))

        payload = list_payments_trail(
            kind='debt_settlement',
            date_from=timezone.localdate().isoformat(),
            date_to=timezone.localdate().isoformat(),
            user=self.manager_user,
        )
        self.assertGreaterEqual(payload['count'], 1)
        row = next(r for r in payload['results'] if r['id'] == txn.id)
        self.assertEqual(row['kind'], 'debt_settlement')
        self.assertEqual(row['payment_method'], 'mpesa')
        self.assertEqual(row['reference'], 'QHXTRAIL01')
        self.assertEqual(row['previous_debt'], '500.00')
        self.assertEqual(row['new_debt'], '300.00')
        self.assertEqual(row['paid_towards'][0]['sale_number'], 'SALE-TRAIL-1')
        self.assertIn('SALE-TRAIL-1', row['paid_towards_label'])

    def test_payments_trail_api(self):
        CustomerService().record_wallet_payment(
            self.customer,
            Decimal('100.00'),
            payment_method='cash',
            user=self.manager_user,
        )
        today = timezone.localdate().isoformat()
        response = self.client.get(
            '/api/sales/customers/payments-trail/',
            {
                'kind': 'debt_settlement',
                'date_from': today,
                'date_to': today,
                'page_size': 10,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn('results', response.data)
        self.assertGreaterEqual(response.data['count'], 1)
        row = response.data['results'][0]
        self.assertEqual(row['kind'], 'debt_settlement')
        self.assertIn('paid_towards', row)
        self.assertIn('previous_debt', row)

    def test_sales_person_cannot_open_payments_trail(self):
        sales_user = User.objects.create_user(username='trail_sales', password='sales123')
        UserProfile.objects.create(
            user=sales_user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        token = RefreshToken.for_user(sales_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        today = timezone.localdate().isoformat()
        response = self.client.get(
            '/api/sales/customers/payments-trail/',
            {'date_from': today, 'date_to': today},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn('0700111222', response.content.decode())

    def test_a_method_card_filters_each_payment_type(self):
        CustomerService().record_wallet_payment(
            self.customer,
            Decimal('80.00'),
            payment_method='cash',
            user=self.manager_user,
        )
        CustomerService().record_wallet_payment(
            self.customer,
            Decimal('40.00'),
            payment_method='mpesa',
            reference='QHXCARD01',
            user=self.manager_user,
        )
        today = timezone.localdate().isoformat()
        window = {'date_from': today, 'date_to': today, 'user': self.manager_user}

        cash = list_payments_trail(kind='debt_settlement', payment_method='cash', **window)
        self.assertGreaterEqual(cash['count'], 1)
        self.assertTrue(all(row['payment_method'] == 'cash' for row in cash['results']))

        mpesa = list_payments_trail(kind='all', payment_method='mpesa', **window)
        self.assertTrue(mpesa['results'])
        self.assertTrue(all(row['payment_method'] == 'mpesa' for row in mpesa['results']))

        for kind in ('all', 'debt_settlement', 'invoice_payment', 'sale_payment'):
            listed = list_payments_trail(kind=kind, payment_method='cash', **window)
            self.assertTrue(all(row['payment_method'] == 'cash' for row in listed['results']))

        junk = list_payments_trail(payment_method='0700111222', **window)
        self.assertEqual(junk['count'], 0)
        self.assertEqual(junk['results'], [])

        for index in range(30):
            CustomerService().record_wallet_payment(
                self.customer,
                Decimal('1.00'),
                payment_method='cash',
                reference=f'CASH{index:02d}',
                user=self.manager_user,
            )
        many = list_payments_trail(
            kind='debt_settlement',
            payment_method='cash',
            page_size=100,
            **window,
        )
        self.assertGreaterEqual(many['count'], 30)
        self.assertTrue(all(row['payment_method'] == 'cash' for row in many['results']))

        response = self.client.get(
            '/api/sales/customers/payments-trail/',
            {
                'kind': 'debt_settlement',
                'payment_method': 'mpesa',
                'date_from': today,
                'date_to': today,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data['results'])
        self.assertTrue(all(row['payment_method'] == 'mpesa' for row in response.data['results']))

        sales_user = User.objects.create_user(username='trail_card_sales', password='sales123')
        UserProfile.objects.create(
            user=sales_user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(sales_user).access_token}'
        )
        denied = self.client.get(
            '/api/sales/customers/payments-trail/',
            {'payment_method': 'cash', 'date_from': today, 'date_to': today},
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(self.customer.phone, denied.content.decode())

        self.client.credentials()
        anonymous = self.client.get(
            '/api/sales/customers/payments-trail/',
            {'payment_method': 'cash'},
        )
        self.assertEqual(anonymous.status_code, status.HTTP_401_UNAUTHORIZED)
