"""Move one completed sale, or one repayment, onto the right customer."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Sum
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import UserProfile
from accounts.role_definitions import ROLE_SALES, ensure_permissions, sync_default_roles
from sales.debt_settlement_correction import transfer_debt_settlement_customer
from sales.models import (
    Customer,
    CustomerWalletTransaction,
    DebtSettlementAllocation,
    Invoice,
    Sale,
)
from sales.sale_customer_transfer import transfer_sale_customer
from sales.services import CustomerService
from settings.models import ModuleFeature, ModuleSettings
from utils.tests.api_test_base import SuperAdminAPITestCase

CUST1_PHONE = '0711888001'
CUST2_PHONE = '0711888002'
CUST3_PHONE = '0711888003'
CUST4_PHONE = '0711888004'


def _debt_sale(customer, cashier, number, total):
    sale = Sale.objects.create(
        sale_number=number,
        status='completed',
        sale_type='pos',
        entry_source='pos',
        customer=customer,
        cashier=cashier,
        subtotal=Decimal(total),
        total=Decimal(total),
        amount_paid=Decimal('0.00'),
        payment_method='on_account',
    )
    CustomerWalletTransaction.objects.create(
        customer=customer,
        transaction_type='debit',
        source_type='debt',
        amount=Decimal(total),
        balance_after=Decimal(total) * -1,
        sale=sale,
        created_by=cashier,
    )
    customer.wallet_balance = Decimal(str(customer.wallet_balance or 0)) - Decimal(total)
    customer.save(update_fields=['wallet_balance', 'updated_at'])
    return sale


def _books(customer):
    """Replay one customer's ledger and the sales that customer owns.

    Args:
        customer: Customer row. Wallet is read again from the database.

    Returns:
        Dict with ``wallet``, ``ledger``, ``unpaid``, and ``unallocated``,
        each a Decimal quantized to 0.01. ``unpaid`` is 0.00 when every
        completed POS sale is fully paid. ``unallocated`` is 0.00 when every
        repayment is sitting on a sale.

    Raises:
        AssertionError: A sale's amount paid is outside 0..total, allocations
        exceed amount paid, the debt row does not match what the sale still
        owes plus what repayments covered, or a repayment points at another
        customer's sale.
    """
    customer.refresh_from_db()
    ledger = Decimal('0.00')
    for row in (
        CustomerWalletTransaction.objects.filter(customer=customer)
        .exclude(source_type='other')
        .order_by('id')
    ):
        amount = Decimal(str(row.amount or 0)).quantize(Decimal('0.01'))
        ledger += amount if row.transaction_type == 'credit' else -amount
    unpaid = Decimal('0.00')
    for sale in Sale.objects.filter(customer=customer, status='completed', sale_type='pos'):
        paid = Decimal(str(sale.amount_paid or 0)).quantize(Decimal('0.01'))
        total = Decimal(str(sale.total or 0)).quantize(Decimal('0.01'))
        if paid < 0 or paid > total:
            raise AssertionError(f'{sale.sale_number} paid {paid} outside 0..{total}')
        allocated = (
            DebtSettlementAllocation.objects.filter(sale=sale).aggregate(total=Sum('amount'))['total']
            or Decimal('0')
        )
        allocated = Decimal(str(allocated)).quantize(Decimal('0.01'))
        if allocated > paid:
            raise AssertionError(f'{sale.sale_number} allocations {allocated} exceed paid {paid}')
        debt = (
            CustomerWalletTransaction.objects.filter(
                sale=sale, source_type='debt', transaction_type='debit'
            ).aggregate(total=Sum('amount'))['total']
            or Decimal('0')
        )
        debt = Decimal(str(debt)).quantize(Decimal('0.01'))
        owing = (total - paid).quantize(Decimal('0.01'))
        if debt != (owing + allocated).quantize(Decimal('0.01')):
            raise AssertionError(
                f'{sale.sale_number} debt {debt} != owing {owing} + allocated {allocated}'
            )
        if CustomerWalletTransaction.objects.filter(sale=sale, source_type='debt').exclude(
            customer=customer
        ).exists():
            raise AssertionError(f'{sale.sale_number} debt is on the wrong customer')
        unpaid += owing
    unallocated = Decimal('0.00')
    for txn in CustomerWalletTransaction.objects.filter(
        customer=customer, source_type='debt_settlement', transaction_type='credit'
    ):
        allocated = (
            DebtSettlementAllocation.objects.filter(wallet_transaction=txn).aggregate(
                total=Sum('amount')
            )['total']
            or Decimal('0')
        )
        unallocated += Decimal(str(txn.amount or 0)) - Decimal(str(allocated or 0))
        for alloc in DebtSettlementAllocation.objects.filter(wallet_transaction=txn).select_related('sale'):
            if alloc.sale.customer_id != customer.pk:
                raise AssertionError(
                    f'Payment {txn.pk} is on {customer.name} but sale {alloc.sale_id} is not'
                )
    return {
        'wallet': Decimal(str(customer.wallet_balance or 0)).quantize(Decimal('0.01')),
        'ledger': ledger.quantize(Decimal('0.01')),
        'unpaid': unpaid.quantize(Decimal('0.01')),
        'unallocated': unallocated.quantize(Decimal('0.01')),
    }


def _assert_books(*customers):
    """Wallet, sales, and repayments for these customers describe the same money.

    Args:
        customers: One or more customers, 1–20. Empty does nothing.

    Returns:
        None.

    Raises:
        AssertionError: Wallet disagrees with the ledger, or the customer
        still owes a sale while part of a repayment has not been applied.
    """
    for customer in customers:
        books = _books(customer)
        if books['wallet'] != books['ledger']:
            raise AssertionError(f"{customer.name} wallet {books['wallet']} != ledger {books['ledger']}")
        if books['unpaid'] > 0 and books['unallocated'] > 0:
            raise AssertionError(
                f"{customer.name} still owes {books['unpaid']} while {books['unallocated']} of a payment is unused"
            )


class IndividualCustomerCorrectionTests(SuperAdminAPITestCase):
    """Payment-only move and sale-only move, with an optional SMS."""

    def setUp(self):
        super().setUp()
        ensure_permissions()
        roles = sync_default_roles(created_by=self.admin)
        self.sales = User.objects.create_user('move_sales_role', password='x')
        UserProfile.objects.create(
            user=self.sales,
            role='cashier',
            custom_role=roles[ROLE_SALES],
            is_active=True,
        )
        self.cust1 = Customer.objects.create(
            name='Customer One', phone=CUST1_PHONE, wallet_balance=Decimal('0.00'), is_active=True,
        )
        self.cust2 = Customer.objects.create(
            name='Customer Two', phone=CUST2_PHONE, wallet_balance=Decimal('0.00'), is_active=True,
        )
        self.cust3 = Customer.objects.create(
            name='Customer Three', phone=CUST3_PHONE, wallet_balance=Decimal('0.00'), is_active=True,
        )
        self.cust4 = Customer.objects.create(
            name='Customer Four', phone=CUST4_PHONE, wallet_balance=Decimal('0.00'), is_active=True,
        )

    def test_payment_of_500_moves_onto_the_customer_who_owed_1000(self):
        """Cust 2 paid 500 by mistake. Cust 1 owed 1000. Only the payment moves."""
        sale1 = _debt_sale(self.cust1, self.sales, 'PAY-1000', '1000.00')
        sale2 = _debt_sale(self.cust2, self.sales, 'PAY-200', '200.00')
        txn = CustomerService().record_wallet_payment(
            customer=self.cust2,
            amount=Decimal('500.00'),
            payment_method='cash',
            user=self.admin,
        )
        with patch(
            'messaging.customer_notify.notify_customer_debt_settlement',
            return_value=object(),
        ) as sms:
            transfer_debt_settlement_customer(
                txn_id=txn.id,
                target_customer_id=self.cust1.id,
                user=self.admin,
                move_sales=False,
                send_sms=True,
            )
        sale1.refresh_from_db()
        sale2.refresh_from_db()
        self.cust1.refresh_from_db()
        self.cust2.refresh_from_db()
        txn.refresh_from_db()
        self.assertEqual(sale2.customer_id, self.cust2.id)
        self.assertEqual(sale2.amount_paid, Decimal('0.00'))
        self.assertEqual(self.cust2.wallet_balance, Decimal('-200.00'))
        self.assertEqual(txn.customer_id, self.cust1.id)
        self.assertEqual(sale1.customer_id, self.cust1.id)
        self.assertEqual(sale1.amount_paid, Decimal('500.00'))
        self.assertEqual(self.cust1.wallet_balance, Decimal('-500.00'))
        self.assertNotIn(CUST1_PHONE, txn.notes)
        self.assertNotIn(CUST2_PHONE, txn.notes)
        sms.assert_called_once()
        _assert_books(self.cust1, self.cust2)

    def test_sale_keyed_to_cust4_moves_to_cust3_without_sms(self):
        sale = _debt_sale(self.cust4, self.sales, 'SALE-C4', '800.00')
        with patch('messaging.customer_notify.notify_customer_sale_completed') as sms:
            result = transfer_sale_customer(
                sale_id=sale.id,
                target_customer_id=self.cust3.id,
                user=self.admin,
                send_sms=False,
            )
        sale.refresh_from_db()
        self.cust3.refresh_from_db()
        self.cust4.refresh_from_db()
        debt = CustomerWalletTransaction.objects.get(sale=sale, source_type='debt')
        self.assertEqual(sale.customer_id, self.cust3.id)
        self.assertEqual(debt.customer_id, self.cust3.id)
        self.assertEqual(self.cust4.wallet_balance, Decimal('0.00'))
        self.assertEqual(self.cust3.wallet_balance, Decimal('-800.00'))
        self.assertFalse(result['sms_sent'])
        sms.assert_not_called()
        self.assertNotIn(CUST3_PHONE, sale.notes or '')
        self.assertNotIn(CUST4_PHONE, sale.notes or '')
        _assert_books(self.cust3, self.cust4)

    def test_api_sale_move_hides_phones_and_blocks_sales_staff(self):
        sale = _debt_sale(self.cust4, self.sales, 'SALE-API', '150.00')
        url = f'/api/sales/{sale.id}/transfer-customer/'
        payload = {'customer_id': self.cust3.id, 'send_sms': False, 'reason': 'Keyed wrong'}
        anon = APIClient()
        anon_res = anon.post(url, payload, format='json')
        self.assertEqual(anon_res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn(CUST4_PHONE, str(anon_res.data))

        clerk = APIClient()
        clerk.force_authenticate(user=self.sales)
        denied = clerk.post(url, payload, format='json')
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(CUST3_PHONE, str(denied.data))

        admin = APIClient()
        admin.force_authenticate(user=self.admin)
        ok = admin.post(url, payload, format='json')
        self.assertEqual(ok.status_code, status.HTTP_200_OK, ok.data)
        body = str(ok.data)
        self.assertNotIn(CUST3_PHONE, body)
        self.assertNotIn(CUST4_PHONE, body)
        self.assertEqual(ok.data['to_customer_name'], 'Customer Three')
        self.assertFalse(ok.data['sms_sent'])

    def test_feature_off_does_not_move_the_sale(self):
        sale = _debt_sale(self.cust4, self.sales, 'SALE-OFF', '40.00')
        module, _ = ModuleSettings.objects.get_or_create(
            module_name='sales',
            defaults={'is_enabled': True},
        )
        was_enabled = module.is_enabled
        module.is_enabled = True
        module.save(update_fields=['is_enabled'])
        feature, _ = ModuleFeature.objects.get_or_create(
            module=module,
            feature_key='transfer_sale_customer',
            defaults={'feature_name': 'Move a sale', 'is_enabled': False},
        )
        feature.is_enabled = False
        feature.save(update_fields=['is_enabled'])
        try:
            client = APIClient()
            client.force_authenticate(user=self.admin)
            res = client.post(
                f'/api/sales/{sale.id}/transfer-customer/',
                {'customer_id': self.cust3.id},
                format='json',
            )
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
            self.assertNotIn(CUST4_PHONE, str(res.data))
            sale.refresh_from_db()
            self.assertEqual(sale.customer_id, self.cust4.id)
        finally:
            feature.is_enabled = True
            feature.save(update_fields=['is_enabled'])
            module.is_enabled = was_enabled
            module.save(update_fields=['is_enabled'])

    def test_eight_sale_moves_keep_one_debt_row(self):
        sale = _debt_sale(self.cust4, self.sales, 'SALE-STRESS', '60.00')
        customers = [self.cust4, self.cust3]
        for step in range(8):
            target = customers[(step + 1) % 2]
            transfer_sale_customer(
                sale_id=sale.id,
                target_customer_id=target.id,
                user=self.admin,
                send_sms=False,
            )
        sale.refresh_from_db()
        self.assertEqual(sale.customer_id, self.cust4.id)
        self.assertEqual(
            CustomerWalletTransaction.objects.filter(sale=sale, source_type='debt').count(),
            1,
        )
        self.cust4.refresh_from_db()
        self.assertEqual(self.cust4.wallet_balance, Decimal('-60.00'))
        _assert_books(self.cust3, self.cust4)

    def _wallet_sum(self):
        total = Decimal('0.00')
        for customer in (self.cust1, self.cust2, self.cust3, self.cust4):
            customer.refresh_from_db()
            total += Decimal(str(customer.wallet_balance or 0))
        return total.quantize(Decimal('0.01'))

    def test_payment_larger_than_the_correct_customers_debt_leaves_credit(self):
        """500 moved onto a customer who only owes 100. 400 stays as credit."""
        sale1 = _debt_sale(self.cust1, self.sales, 'EDGE-100', '100.00')
        _debt_sale(self.cust2, self.sales, 'EDGE-200', '200.00')
        txn = CustomerService().record_wallet_payment(
            customer=self.cust2, amount=Decimal('500.00'), payment_method='cash', user=self.admin,
        )
        before = self._wallet_sum()
        transfer_debt_settlement_customer(
            txn_id=txn.id, target_customer_id=self.cust1.id, user=self.admin, move_sales=False,
        )
        sale1.refresh_from_db()
        self.cust1.refresh_from_db()
        self.cust2.refresh_from_db()
        self.assertEqual(sale1.amount_paid, Decimal('100.00'))
        self.assertEqual(self.cust1.wallet_balance, Decimal('400.00'))
        self.assertEqual(self.cust2.wallet_balance, Decimal('-200.00'))
        self.assertEqual(self._wallet_sum(), before)
        _assert_books(self.cust1, self.cust2)

    def test_payment_sits_as_credit_when_the_correct_customer_has_no_debt(self):
        _debt_sale(self.cust2, self.sales, 'EDGE-NODEBT', '200.00')
        txn = CustomerService().record_wallet_payment(
            customer=self.cust2, amount=Decimal('500.00'), payment_method='cash', user=self.admin,
        )
        before = self._wallet_sum()
        transfer_debt_settlement_customer(
            txn_id=txn.id, target_customer_id=self.cust1.id, user=self.admin, move_sales=False,
        )
        self.cust1.refresh_from_db()
        self.cust2.refresh_from_db()
        self.assertEqual(self.cust1.wallet_balance, Decimal('500.00'))
        self.assertEqual(self.cust2.wallet_balance, Decimal('-200.00'))
        self.assertEqual(Sale.objects.filter(customer=self.cust1).count(), 0)
        self.assertEqual(self._wallet_sum(), before)
        _assert_books(self.cust1, self.cust2)

    def test_payment_spread_across_two_sales_returns_both_debts(self):
        """500 cleared 200 then 300 of a second sale. Both debts come back."""
        first = _debt_sale(self.cust2, self.sales, 'EDGE-A', '200.00')
        second = _debt_sale(self.cust2, self.sales, 'EDGE-B', '400.00')
        target = _debt_sale(self.cust1, self.sales, 'EDGE-T', '1000.00')
        txn = CustomerService().record_wallet_payment(
            customer=self.cust2, amount=Decimal('500.00'), payment_method='cash', user=self.admin,
        )
        before = self._wallet_sum()
        self.assertEqual(Sale.objects.get(pk=first.pk).amount_paid, Decimal('200.00'))
        transfer_debt_settlement_customer(
            txn_id=txn.id, target_customer_id=self.cust1.id, user=self.admin, move_sales=False,
        )
        first.refresh_from_db()
        second.refresh_from_db()
        target.refresh_from_db()
        self.assertEqual(first.customer_id, self.cust2.id)
        self.assertEqual(second.customer_id, self.cust2.id)
        self.assertEqual(first.amount_paid, Decimal('0.00'))
        self.assertEqual(second.amount_paid, Decimal('0.00'))
        self.assertEqual(target.amount_paid, Decimal('500.00'))
        self.assertEqual(target.customer_id, self.cust1.id)
        self.cust2.refresh_from_db()
        self.assertEqual(self.cust2.wallet_balance, Decimal('-600.00'))
        self.assertEqual(self._wallet_sum(), before)
        _assert_books(self.cust1, self.cust2)

    def test_older_sale_is_paid_before_the_newer_one(self):
        older = _debt_sale(self.cust1, self.sales, 'EDGE-OLD', '600.00')
        newer = _debt_sale(self.cust1, self.sales, 'EDGE-NEW', '400.00')
        _debt_sale(self.cust2, self.sales, 'EDGE-SRC', '200.00')
        txn = CustomerService().record_wallet_payment(
            customer=self.cust2, amount=Decimal('500.00'), payment_method='cash', user=self.admin,
        )
        transfer_debt_settlement_customer(
            txn_id=txn.id, target_customer_id=self.cust1.id, user=self.admin, move_sales=False,
        )
        older.refresh_from_db()
        newer.refresh_from_db()
        self.assertEqual(older.amount_paid, Decimal('500.00'))
        self.assertEqual(newer.amount_paid, Decimal('0.00'))
        self.cust1.refresh_from_db()
        self.assertEqual(self.cust1.wallet_balance, Decimal('-500.00'))
        _assert_books(self.cust1, self.cust2)

    def test_one_of_two_payments_moves_and_the_other_stays(self):
        sale = _debt_sale(self.cust2, self.sales, 'EDGE-TWO', '1000.00')
        target = _debt_sale(self.cust1, self.sales, 'EDGE-TWO-T', '1000.00')
        first = CustomerService().record_wallet_payment(
            customer=self.cust2, amount=Decimal('400.00'), payment_method='cash', user=self.admin,
        )
        second = CustomerService().record_wallet_payment(
            customer=self.cust2, amount=Decimal('300.00'), payment_method='cash', user=self.admin,
        )
        before = self._wallet_sum()
        transfer_debt_settlement_customer(
            txn_id=first.id, target_customer_id=self.cust1.id, user=self.admin, move_sales=False,
        )
        sale.refresh_from_db()
        target.refresh_from_db()
        second.refresh_from_db()
        first.refresh_from_db()
        self.assertEqual(first.customer_id, self.cust1.id)
        self.assertEqual(second.customer_id, self.cust2.id)
        self.assertEqual(sale.customer_id, self.cust2.id)
        self.assertEqual(sale.amount_paid, Decimal('300.00'))
        self.assertEqual(target.amount_paid, Decimal('400.00'))
        self.assertEqual(self._wallet_sum(), before)
        _assert_books(self.cust1, self.cust2)

    def test_extra_payment_pays_the_correct_customers_other_sale(self):
        """Sale of 200 moves with a 500 payment. The spare 300 pays the 1,000 debt."""
        own = _debt_sale(self.cust1, self.sales, 'EDGE-OWN', '1000.00')
        moved = _debt_sale(self.cust2, self.sales, 'EDGE-MOVED', '200.00')
        txn = CustomerService().record_wallet_payment(
            customer=self.cust2, amount=Decimal('500.00'), payment_method='cash', user=self.admin,
        )
        before = self._wallet_sum()
        transfer_debt_settlement_customer(
            txn_id=txn.id, target_customer_id=self.cust1.id, user=self.admin, move_sales=True,
        )
        own.refresh_from_db()
        moved.refresh_from_db()
        self.cust1.refresh_from_db()
        self.cust2.refresh_from_db()
        self.assertEqual(moved.customer_id, self.cust1.id)
        self.assertEqual(moved.amount_paid, Decimal('200.00'))
        self.assertEqual(own.customer_id, self.cust1.id)
        self.assertEqual(own.amount_paid, Decimal('300.00'))
        self.assertEqual(self.cust2.wallet_balance, Decimal('0.00'))
        self.assertEqual(self.cust1.wallet_balance, Decimal('-700.00'))
        self.assertEqual(self._wallet_sum(), before)
        _assert_books(self.cust1, self.cust2)

    def test_sale_move_leaves_the_payment_on_the_old_customer(self):
        """800 sale moves to customer 3. The 200 payment stays and clears the other 100 sale."""
        moving = _debt_sale(self.cust4, self.sales, 'EDGE-MV', '800.00')
        other = _debt_sale(self.cust4, self.sales, 'EDGE-STAY', '100.00')
        txn = CustomerService().record_wallet_payment(
            customer=self.cust4, amount=Decimal('200.00'), payment_method='cash', user=self.admin,
        )
        before = self._wallet_sum()
        transfer_sale_customer(
            sale_id=moving.id, target_customer_id=self.cust3.id, user=self.admin, send_sms=False,
        )
        moving.refresh_from_db()
        other.refresh_from_db()
        txn.refresh_from_db()
        self.cust3.refresh_from_db()
        self.cust4.refresh_from_db()
        self.assertEqual(moving.customer_id, self.cust3.id)
        self.assertEqual(moving.amount_paid, Decimal('0.00'))
        self.assertEqual(txn.customer_id, self.cust4.id)
        self.assertEqual(other.customer_id, self.cust4.id)
        self.assertEqual(other.amount_paid, Decimal('100.00'))
        self.assertEqual(self.cust3.wallet_balance, Decimal('-800.00'))
        self.assertEqual(self.cust4.wallet_balance, Decimal('100.00'))
        self.assertEqual(self._wallet_sum(), before)
        _assert_books(self.cust3, self.cust4)

    def test_cash_sale_changes_customer_without_touching_wallets(self):
        sale = Sale.objects.create(
            sale_number='EDGE-CASH',
            status='completed',
            sale_type='pos',
            entry_source='pos',
            customer=self.cust4,
            cashier=self.sales,
            subtotal=Decimal('250.00'),
            total=Decimal('250.00'),
            amount_paid=Decimal('250.00'),
            payment_method='cash',
        )
        before = self._wallet_sum()
        transfer_sale_customer(
            sale_id=sale.id, target_customer_id=self.cust3.id, user=self.admin,
        )
        sale.refresh_from_db()
        self.assertEqual(sale.customer_id, self.cust3.id)
        self.assertEqual(sale.amount_paid, Decimal('250.00'))
        self.assertFalse(
            CustomerWalletTransaction.objects.filter(sale=sale, source_type='debt').exists()
        )
        self.assertEqual(self._wallet_sum(), before)
        _assert_books(self.cust3, self.cust4)

    def test_part_paid_at_checkout_keeps_that_cash_on_the_sale(self):
        sale = Sale.objects.create(
            sale_number='EDGE-PART',
            status='completed',
            sale_type='pos',
            entry_source='pos',
            customer=self.cust4,
            cashier=self.sales,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            amount_paid=Decimal('300.00'),
            payment_method='cash',
        )
        CustomerWalletTransaction.objects.create(
            customer=self.cust4,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('700.00'),
            balance_after=Decimal('-700.00'),
            sale=sale,
            created_by=self.sales,
        )
        self.cust4.wallet_balance = Decimal('-700.00')
        self.cust4.save(update_fields=['wallet_balance', 'updated_at'])
        before = self._wallet_sum()
        transfer_sale_customer(
            sale_id=sale.id, target_customer_id=self.cust3.id, user=self.admin,
        )
        sale.refresh_from_db()
        self.cust3.refresh_from_db()
        self.cust4.refresh_from_db()
        self.assertEqual(sale.amount_paid, Decimal('300.00'))
        self.assertEqual(sale.customer_id, self.cust3.id)
        self.assertEqual(self.cust3.wallet_balance, Decimal('-700.00'))
        self.assertEqual(self.cust4.wallet_balance, Decimal('0.00'))
        self.assertEqual(self._wallet_sum(), before)
        _assert_books(self.cust3, self.cust4)

    def test_sale_then_payment_end_on_the_same_customer(self):
        """Move the sale, then move the payment that had been left behind."""
        moving = _debt_sale(self.cust4, self.sales, 'EDGE-SEQ', '800.00')
        other = _debt_sale(self.cust4, self.sales, 'EDGE-SEQ-B', '100.00')
        txn = CustomerService().record_wallet_payment(
            customer=self.cust4, amount=Decimal('200.00'), payment_method='cash', user=self.admin,
        )
        before = self._wallet_sum()
        transfer_sale_customer(
            sale_id=moving.id, target_customer_id=self.cust3.id, user=self.admin,
        )
        transfer_debt_settlement_customer(
            txn_id=txn.id, target_customer_id=self.cust3.id, user=self.admin, move_sales=False,
        )
        moving.refresh_from_db()
        other.refresh_from_db()
        txn.refresh_from_db()
        self.cust3.refresh_from_db()
        self.cust4.refresh_from_db()
        self.assertEqual(moving.customer_id, self.cust3.id)
        self.assertEqual(moving.amount_paid, Decimal('200.00'))
        self.assertEqual(txn.customer_id, self.cust3.id)
        self.assertEqual(other.customer_id, self.cust4.id)
        self.assertEqual(other.amount_paid, Decimal('0.00'))
        self.assertEqual(self.cust4.wallet_balance, Decimal('-100.00'))
        self.assertEqual(self.cust3.wallet_balance, Decimal('-600.00'))
        self.assertEqual(self._wallet_sum(), before)
        _assert_books(self.cust3, self.cust4)

    def test_invoice_follows_the_sale(self):
        sale = _debt_sale(self.cust4, self.sales, 'EDGE-INV', '800.00')
        invoice = Invoice.objects.create(
            sale=sale,
            customer=self.cust4,
            subtotal=Decimal('800.00'),
            total=Decimal('800.00'),
            amount_paid=Decimal('0.00'),
            created_by=self.admin,
        )
        transfer_sale_customer(
            sale_id=sale.id, target_customer_id=self.cust3.id, user=self.admin,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.customer_id, self.cust3.id)
        self.assertEqual(invoice.customer_name, 'Customer Three')
        self.assertEqual(invoice.customer_phone, CUST3_PHONE)
        _assert_books(self.cust3, self.cust4)

    def test_refused_moves_do_not_change_balances(self):
        sale = _debt_sale(self.cust4, self.sales, 'EDGE-HOLD', '80.00')
        holding = Sale.objects.create(
            sale_number='EDGE-HOLDING',
            status='holding',
            sale_type='pos',
            entry_source='pos',
            customer=self.cust4,
            cashier=self.sales,
            subtotal=Decimal('10.00'),
            total=Decimal('10.00'),
            amount_paid=Decimal('0.00'),
            payment_method='on_account',
        )
        before = self._wallet_sum()
        sale_paid = sale.amount_paid
        with self.assertRaises(ValidationError):
            transfer_sale_customer(
                sale_id=holding.id, target_customer_id=self.cust3.id, user=self.admin,
            )
        with self.assertRaises(ValidationError):
            transfer_sale_customer(
                sale_id=sale.id, target_customer_id=self.cust4.id, user=self.admin,
            )
        self.cust3.is_active = False
        self.cust3.save(update_fields=['is_active'])
        with self.assertRaises(ValidationError):
            transfer_sale_customer(
                sale_id=sale.id, target_customer_id=self.cust3.id, user=self.admin,
            )
        self.cust3.is_active = True
        self.cust3.save(update_fields=['is_active'])
        holding.refresh_from_db()
        sale.refresh_from_db()
        self.assertEqual(holding.customer_id, self.cust4.id)
        self.assertEqual(sale.customer_id, self.cust4.id)
        self.assertEqual(sale.amount_paid, sale_paid)
        self.assertEqual(self._wallet_sum(), before)
        _assert_books(self.cust3, self.cust4)
