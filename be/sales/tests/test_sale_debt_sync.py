"""Repair helper for sale debt left stale after admin correction."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from io import StringIO

from sales.models import Customer, CustomerWalletTransaction, Sale
from sales.sale_debt_sync import sync_sale_customer_debt


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
