"""Regression: money-in must not double-count debt settlements as sale tender."""

from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from products.models import Category, Product
from sales.daily_sales import get_daily_sales_report
from sales.models import Customer, CustomerWalletTransaction, Sale, SaleItem
from sales.payments_trail import list_payments_trail, summarize_payments_trail
from sales.sale_debt_sync import sale_checkout_tender_amount
from sales.services import CustomerService
from utils.tests.api_test_base import ManagerAPITestCase


class PaymentDoubleCountTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            name='Double Count',
            phone='0700555666',
            wallet_balance=Decimal('-500.00'),
            is_active=True,
        )
        category = Category.objects.create(name='DC', is_active=True)
        self.product = Product.objects.create(
            name='DC Item',
            sku='DC-1',
            category=category,
            price=Decimal('500'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )
        self.sale = Sale.objects.create(
            sale_number='SALE-DC-1',
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

    def test_settlement_does_not_double_trail_or_daily_cash(self):
        CustomerService().record_wallet_payment(
            self.customer,
            Decimal('500.00'),
            payment_method='mpesa',
            reference='QHXDC500',
            user=self.manager_user,
        )
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.amount_paid, Decimal('500.00'))
        self.assertEqual(sale_checkout_tender_amount(self.sale), Decimal('0.00'))

        today = timezone.localdate().isoformat()
        trail = list_payments_trail(
            kind='all',
            date_from=today,
            date_to=today,
            page_size=100,
            user=self.manager_user,
        )
        kinds = {row['kind'] for row in trail['results']}
        self.assertIn('debt_settlement', kinds)
        self.assertNotIn('sale_payment', kinds)

        summary = summarize_payments_trail(
            date_from=today,
            date_to=today,
            user=self.manager_user,
        )
        self.assertEqual(Decimal(summary['total_amount']), Decimal('500.00'))

        daily = get_daily_sales_report(date_str=today, user=self.manager_user)
        self.assertEqual(Decimal(daily['summary']['total_paid']), Decimal('0.00'))
        self.assertEqual(Decimal(daily['summary']['total_debt_collected']), Decimal('500.00'))
        self.assertEqual(Decimal(daily['summary']['total_collected']), Decimal('500.00'))

    def test_partial_tender_plus_settlement_counts_once_each(self):
        self.sale.amount_paid = Decimal('100.00')
        self.sale.save(update_fields=['amount_paid'])
        # Refresh wallet debt to remaining 400
        self.customer.wallet_balance = Decimal('-400.00')
        self.customer.save(update_fields=['wallet_balance'])
        CustomerWalletTransaction.objects.filter(
            sale=self.sale, source_type='debt'
        ).update(amount=Decimal('400.00'), balance_after=Decimal('-400.00'))

        CustomerService().record_wallet_payment(
            self.customer,
            Decimal('200.00'),
            payment_method='cash',
            user=self.manager_user,
        )
        self.sale.refresh_from_db()
        self.assertEqual(sale_checkout_tender_amount(self.sale), Decimal('100.00'))

        today = timezone.localdate().isoformat()
        summary = summarize_payments_trail(
            date_from=today,
            date_to=today,
            user=self.manager_user,
        )
        # 100 checkout tender + 200 settlement = 300 (not 100+200+300)
        self.assertEqual(Decimal(summary['total_amount']), Decimal('300.00'))

    def test_summary_api_matches_single_count(self):
        CustomerService().record_wallet_payment(
            self.customer,
            Decimal('500.00'),
            payment_method='mpesa',
            user=self.manager_user,
        )
        today = timezone.localdate().isoformat()
        response = self.client.get(
            '/api/sales/customers/payments-trail/summary/',
            {'date_from': today, 'date_to': today},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(Decimal(response.data['total_amount']), Decimal('500.00'))

    def test_kogi_style_one_collection_not_two_rows(self):
        """Debt sale + later M-Pesa collection must not also list Sale tender."""
        CustomerService().record_wallet_payment(
            self.customer,
            Decimal('500.00'),
            payment_method='mpesa',
            reference='UK5PL0DB7H',
            user=self.manager_user,
        )
        today = timezone.localdate().isoformat()
        trail = list_payments_trail(
            kind='all',
            date_from=today,
            date_to=today,
            page_size=100,
            user=self.manager_user,
            search='Double',
        )
        sale_rows = [r for r in trail['results'] if r['kind'] == 'sale_payment']
        settle_rows = [r for r in trail['results'] if r['kind'] == 'debt_settlement']
        self.assertEqual(len(settle_rows), 1)
        self.assertEqual(Decimal(settle_rows[0]['amount']), Decimal('500.00'))
        self.assertEqual(sale_rows, [])
        self.assertEqual(trail['count'], 1)

    def test_backfill_allocations_hides_orphan_sale_tender(self):
        """Historical bump without allocation → trail doubles until backfill."""
        from sales.models import DebtSettlementAllocation
        from sales.sale_debt_sync import backfill_missing_settlement_allocations

        txn = CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('500.00'),
            balance_after=Decimal('0.00'),
            payment_method='mpesa',
            reference='ORPHAN-1',
            created_by=self.manager_user,
        )
        self.customer.wallet_balance = Decimal('0.00')
        self.customer.save(update_fields=['wallet_balance'])
        # Simulate legacy reconcile: amount_paid bumped, no allocation row.
        self.sale.amount_paid = Decimal('500.00')
        self.sale.save(update_fields=['amount_paid'])
        self.assertEqual(
            DebtSettlementAllocation.objects.filter(wallet_transaction=txn).count(),
            0,
        )
        today = timezone.localdate().isoformat()
        before = summarize_payments_trail(
            date_from=today, date_to=today, user=self.manager_user
        )
        self.assertEqual(Decimal(before['total_amount']), Decimal('1000.00'))

        result = backfill_missing_settlement_allocations(
            customer_id=self.customer.id
        )
        self.assertGreaterEqual(result['allocations_created'], 1)
        after = summarize_payments_trail(
            date_from=today, date_to=today, user=self.manager_user
        )
        self.assertEqual(Decimal(after['total_amount']), Decimal('500.00'))
