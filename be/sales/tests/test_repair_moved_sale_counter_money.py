"""One-time command: counter money left behind when a sale was moved."""

from decimal import Decimal
from io import StringIO

from django.core.management import call_command

from sales.models import Customer, CustomerWalletTransaction
from sales.services import CustomerService
from sales.tests.test_sale_customer_transfer import _assert_books, _debt_sale
from utils.tests.api_test_base import SuperAdminAPITestCase

OLD_PHONE = '0711666001'
NEW_PHONE = '0711666002'


class RepairMovedSaleCounterMoneyTests(SuperAdminAPITestCase):
    """The command moves counter rows and leaves a later repayment where it is."""

    def setUp(self):
        super().setUp()
        self.old = Customer.objects.create(
            name='Old Duka', phone=OLD_PHONE, wallet_balance=Decimal('0.00'), is_active=True,
        )
        self.new = Customer.objects.create(
            name='New Duka', phone=NEW_PHONE, wallet_balance=Decimal('0.00'), is_active=True,
        )

    def _moved_sale(self, number, total='1500.00'):
        sale = _debt_sale(self.old, self.admin, number, total)
        sale.customer = self.new
        sale.notes = 'Moved from Old Duka to New Duka'
        sale.save(update_fields=['customer', 'notes', 'updated_at'])
        return sale

    def test_dry_run_prints_the_row_and_writes_nothing(self):
        sale = self._moved_sale('CMD-DRY')
        out = StringIO()
        call_command('repair_moved_sale_counter_money', stdout=out)
        text = out.getvalue()
        self.assertIn('CMD-DRY', text)
        self.assertIn('DRY-RUN', text)
        self.assertNotIn(OLD_PHONE, text)
        self.assertNotIn(NEW_PHONE, text)
        debt = CustomerWalletTransaction.objects.get(sale=sale, source_type='debt')
        self.assertEqual(debt.customer_id, self.old.id)

    def test_apply_moves_counter_debt_and_leaves_a_later_repayment(self):
        sale = self._moved_sale('CMD-APPLY')
        txn = CustomerService().record_wallet_payment(
            customer=self.old, amount=Decimal('500.00'), payment_method='cash', user=self.admin,
        )
        out = StringIO()
        call_command('repair_moved_sale_counter_money', '--apply', stdout=out)
        debt = CustomerWalletTransaction.objects.get(sale=sale, source_type='debt')
        txn.refresh_from_db()
        self.old.refresh_from_db()
        self.new.refresh_from_db()
        self.assertEqual(debt.customer_id, self.new.id)
        self.assertEqual(txn.customer_id, self.old.id)
        self.assertNotIn(OLD_PHONE, out.getvalue())
        self.assertEqual(self.new.wallet_balance, Decimal('-1500.00'))
        _assert_books(self.old, self.new)

    def test_a_sale_that_was_not_moved_is_left_alone(self):
        sale = _debt_sale(self.old, self.admin, 'CMD-STAY', '40.00')
        sale.customer = self.new
        sale.save(update_fields=['customer', 'updated_at'])
        call_command('repair_moved_sale_counter_money', '--apply', stdout=StringIO())
        debt = CustomerWalletTransaction.objects.get(sale=sale, source_type='debt')
        self.assertEqual(debt.customer_id, self.old.id)

    def test_eight_moved_sales_are_fixed_together(self):
        sales = [self._moved_sale(f'CMD-{index}', '40.00') for index in range(8)]
        call_command('repair_moved_sale_counter_money', '--apply', stdout=StringIO())
        for sale in sales:
            self.assertEqual(
                CustomerWalletTransaction.objects.get(sale=sale, source_type='debt').customer_id,
                self.new.id,
            )
        self.new.refresh_from_db()
        self.old.refresh_from_db()
        self.assertEqual(self.new.wallet_balance, Decimal('-320.00'))
        self.assertEqual(self.old.wallet_balance, Decimal('0.00'))
        _assert_books(self.old, self.new)
