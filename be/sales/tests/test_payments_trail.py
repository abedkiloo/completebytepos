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
