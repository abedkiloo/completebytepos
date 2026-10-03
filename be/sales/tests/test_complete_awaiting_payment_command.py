"""complete_awaiting_payment_sales finishes sales left by the retired collect step."""

from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_COMPLETE
from products.models import Category, Product
from sales.models import Customer, CustomerWalletTransaction, Sale, SaleItem


class CompleteAwaitingPaymentCommandTests(TestCase):
    def setUp(self):
        self.cashier = User.objects.create_user('collect_till', password='x')
        self.manager = User.objects.create_user('collect_mgr', password='x')
        category = Category.objects.create(name='Collect Cat')
        self.product = Product.objects.create(
            name='Collect Item',
            sku='COLLECT-1',
            category=category,
            price=Decimal('100.00'),
            cost=Decimal('40.00'),
            stock_quantity=10,
            track_stock=True,
        )

    def _sale(self, number, *, paid, customer=None, sale_type='pos'):
        sale = Sale.objects.create(
            sale_number=number,
            status='awaiting_payment',
            sale_type=sale_type,
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
            payment_method='cash',
            amount_paid=Decimal(paid),
            customer=customer,
            cashier=self.cashier,
            occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100.00'),
            subtotal=Decimal('100.00'),
        )
        return sale

    def _run(self, *args):
        out = StringIO()
        call_command('complete_awaiting_payment_sales', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        sale = self._sale('AW-DRY', paid='100.00')
        output = self._run('--dry-run')
        self.assertIn('would complete', output)
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'awaiting_payment')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)

    def test_fully_paid_sale_is_completed_and_stock_moves(self):
        sale = self._sale('AW-PAID', paid='100.00')
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            entity_repr=sale.sale_number,
            status=PendingChange.STATUS_APPROVED,
            checked_by=self.manager,
            apply_payload={'payment_method': 'mpesa', 'amount_paid': '100.00',
                           'payment_reference': 'QWE123'},
        )
        output = self._run()
        self.assertIn('Completed 1 sale(s)', output)
        self.assertIn('recorded by collect_mgr', output)
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'completed')
        self.assertEqual(sale.payment_method, 'mpesa')
        self.assertEqual(sale.payment_reference, 'QWE123')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 9)

    def test_short_payment_with_customer_becomes_debt(self):
        customer = Customer.objects.create(name='Short Payer', phone='0700111222')
        sale = self._sale('AW-SHORT', paid='30.00', customer=customer)
        self._run()
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'completed')
        customer.refresh_from_db()
        self.assertEqual(customer.wallet_balance, Decimal('-70.00'))
        self.assertTrue(
            CustomerWalletTransaction.objects.filter(sale=sale, source_type='debt').exists()
        )

    def test_short_normal_sale_gets_an_invoice(self):
        customer = Customer.objects.create(name='Invoice Payer', phone='0700111333')
        sale = self._sale('AW-NORMAL', paid='40.00', customer=customer, sale_type='normal')
        self._run()
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'completed')
        invoice = sale.invoices.get()
        self.assertEqual(invoice.balance, Decimal('60.00'))

    def test_short_payment_without_customer_is_skipped(self):
        sale = self._sale('AW-WALKIN', paid='0')
        output = self._run()
        self.assertIn('skipped', output)
        self.assertIn('--assume-paid-in-full', output)
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'awaiting_payment')

    def test_assume_paid_in_full(self):
        sale = self._sale('AW-ASSUME', paid='0')
        self._run('--assume-paid-in-full', '--user', 'collect_mgr')
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'completed')
        self.assertEqual(sale.amount_paid, Decimal('100.00'))

    def test_only_selected_sale(self):
        first = self._sale('AW-ONE', paid='100.00')
        second = self._sale('AW-TWO', paid='100.00')
        self._run('--sale', 'AW-ONE')
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, 'completed')
        self.assertEqual(second.status, 'awaiting_payment')

    def test_pending_change_is_marked_approved(self):
        sale = self._sale('AW-PENDING', paid='100.00')
        change = PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            entity_repr=sale.sale_number,
            status=PendingChange.STATUS_PENDING,
            apply_payload={'amount_paid': '100.00'},
        )
        self._run('--user', 'collect_mgr')
        change.refresh_from_db()
        self.assertEqual(change.status, PendingChange.STATUS_APPROVED)
        self.assertEqual(change.checked_by, self.manager)

    def test_unknown_user_errors(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self._run('--user', 'nobody_here')
