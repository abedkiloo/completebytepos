"""Repair helper for sale debt left stale after admin correction."""

from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from sales.customer_detail import get_customer_detail
from sales.debt_management import list_debtors
from sales.models import Customer, CustomerWalletTransaction, Sale
from sales.sale_debt_sync import (
    apply_settlement_to_underpaid_sales,
    reconcile_sale_payments_with_wallet,
    sync_sale_customer_debt,
)
from sales.services import CustomerService


class SaleDebtSyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('debt_fix', password='x')
        self.customer = Customer.objects.create(
            name='Stuck Debtor', phone='0700111222', wallet_balance=Decimal('0'),
        )
        self.sale = Sale.objects.create(
            sale_number='SALE-DEBT-FIX',
            status='completed',
            sale_type='pos',
            customer=self.customer,
            subtotal=Decimal('176000.00'),
            discount_amount=Decimal('5500.00'),
            total=Decimal('170500.00'),
            amount_paid=Decimal('0'),
            payment_method='other',
            cashier=self.user,
        )
        # Bug shape: stale debt row still marked active, but wallet was reversed to 0.
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('176000.00'),
            balance_after=Decimal('-176000.00'),
            sale=self.sale,
            reference=self.sale.sale_number,
            notes='Original pre-correction debt',
            created_by=self.user,
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='credit',
            source_type='other',
            amount=Decimal('176000.00'),
            balance_after=Decimal('0.00'),
            sale=self.sale,
            reference=self.sale.sale_number,
            notes='Admin returned sale for correction',
            created_by=self.user,
        )

    def test_sync_posts_corrected_unpaid_onto_wallet(self):
        result = sync_sale_customer_debt(self.sale, user=self.user)
        self.assertEqual(result['action'], 'debt_synced')
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('-170500.00'))
        active = CustomerWalletTransaction.objects.filter(
            sale=self.sale, source_type='debt',
        )
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.get().amount, Decimal('170500.00'))

    def test_repair_command_dry_run_and_apply(self):
        out = StringIO()
        call_command('repair_sale_debt', '--sale', 'SALE-DEBT-FIX', stdout=out)
        self.assertIn('DRY-RUN', out.getvalue())
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('0'))

        out = StringIO()
        call_command(
            'repair_sale_debt', '--sale', 'SALE-DEBT-FIX', '--apply', stdout=out,
        )
        self.assertIn('debt_synced', out.getvalue())
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('-170500.00'))


class SettlementUpdatesSaleAmountPaidTests(TestCase):
    """Wallet settlement must clear order debt so profile Orders match debtors."""

    def setUp(self):
        self.user = User.objects.create_user('settle_fix', password='x')
        self.customer = Customer.objects.create(
            name='SAM',
            phone='254704511478',
            customer_code='CUST-000196',
            wallet_balance=Decimal('-1000.00'),
            is_active=True,
        )
        self.sale = Sale.objects.create(
            sale_number='SALE-798115BA',
            status='completed',
            sale_type='pos',
            customer=self.customer,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            amount_paid=Decimal('0'),
            payment_method='cash',
            cashier=self.user,
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('1000.00'),
            balance_after=Decimal('-1000.00'),
            sale=self.sale,
            reference=self.sale.sale_number,
            notes='Pay later',
            created_by=self.user,
        )

    def test_full_settlement_marks_sale_paid_and_drops_from_debtors(self):
        CustomerService().record_wallet_payment(
            self.customer,
            Decimal('1000.00'),
            payment_method='cash',
            user=self.user,
        )
        self.customer.refresh_from_db()
        self.sale.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('0.00'))
        self.assertEqual(self.sale.amount_paid, Decimal('1000.00'))

        results, count = list_debtors(search='SAM')
        self.assertEqual(count, 0)
        self.assertEqual(results, [])

        detail = get_customer_detail(customer_id=self.customer.id)
        order = detail['orders'][0]
        self.assertEqual(order['payment_status'], 'paid')
        self.assertEqual(Decimal(order['debt_amount']), Decimal('0.00'))
        self.assertEqual(
            Decimal(detail['standing_summary']['wallet_debt']), Decimal('0.00')
        )

    def test_partial_settlement_reduces_sale_debt(self):
        applied = apply_settlement_to_underpaid_sales(self.customer, Decimal('400.00'))
        self.assertEqual(applied, Decimal('400.00'))
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.amount_paid, Decimal('400.00'))

    def test_profile_reconciles_historical_settlement_without_amount_paid(self):
        # Settlement already on the wallet; sale.amount_paid never bumped (SAM bug).
        self.customer.wallet_balance = Decimal('0.00')
        self.customer.save(update_fields=['wallet_balance', 'updated_at'])
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('1000.00'),
            balance_after=Decimal('0.00'),
            notes='Debt payment received via Cash',
            created_by=self.user,
        )
        self.assertEqual(reconcile_sale_payments_with_wallet(self.customer), 1)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.amount_paid, Decimal('1000.00'))

        detail = get_customer_detail(customer_id=self.customer.id)
        self.assertEqual(detail['orders'][0]['payment_status'], 'paid')
        results, count = list_debtors(search='SAM')
        self.assertEqual(count, 0)
        self.assertEqual(results, [])
