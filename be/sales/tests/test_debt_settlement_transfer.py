"""Move a posted debt repayment onto the customer who actually paid."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import UserProfile
from accounts.role_definitions import (
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from sales.debt_settlement_correction import transfer_debt_settlement_customer
from sales.models import Customer, CustomerWalletTransaction, DebtSettlementAllocation, Sale
from sales.services import CustomerService
from settings.models import ModuleFeature, ModuleSettings
from utils.tests.api_test_base import SuperAdminAPITestCase

WRONG_PHONE = '0711999001'
RIGHT_PHONE = '0711999002'


def _debt_sale(customer, cashier, number, total='100.00'):
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


class DebtSettlementTransferTests(SuperAdminAPITestCase):
    """Repayment customer transfer: books, permission, and the feature switch."""

    def setUp(self):
        super().setUp()
        ensure_permissions()
        roles = sync_default_roles(created_by=self.admin)
        self.sales = User.objects.create_user('xfer_sales', password='x')
        UserProfile.objects.create(
            user=self.sales,
            role='cashier',
            custom_role=roles[ROLE_SALES],
            is_active=True,
        )
        self.wrong = Customer.objects.create(
            name='Wrong Shop',
            phone=WRONG_PHONE,
            wallet_balance=Decimal('0.00'),
            is_active=True,
        )
        self.right = Customer.objects.create(
            name='Right Shop',
            phone=RIGHT_PHONE,
            wallet_balance=Decimal('0.00'),
            is_active=True,
        )
        self.sale = _debt_sale(self.wrong, self.sales, 'XFER-1')
        self.right_sale = _debt_sale(self.right, self.sales, 'XFER-RIGHT')
        self.txn = CustomerService().record_wallet_payment(
            customer=self.wrong,
            amount=Decimal('100.00'),
            payment_method='cash',
            user=self.admin,
        )
        self.wrong.refresh_from_db()
        self.sale.refresh_from_db()

    def test_payment_only_puts_the_money_on_the_right_customer(self):
        """The repayment leaves the wrong shop and pays the right shop's sale."""
        result = transfer_debt_settlement_customer(
            txn_id=self.txn.id,
            target_customer_id=self.right.id,
            user=self.admin,
            reason='Keyed on the wrong shop',
            move_sales=False,
        )
        self.wrong.refresh_from_db()
        self.right.refresh_from_db()
        self.sale.refresh_from_db()
        self.right_sale.refresh_from_db()
        self.txn.refresh_from_db()
        self.assertEqual(result['transaction'].customer_id, self.right.id)
        self.assertEqual(self.sale.customer_id, self.wrong.id)
        self.assertEqual(self.sale.amount_paid, Decimal('0.00'))
        self.assertEqual(self.wrong.wallet_balance, Decimal('-100.00'))
        self.assertEqual(self.right_sale.amount_paid, Decimal('100.00'))
        self.assertEqual(self.right.wallet_balance, Decimal('0.00'))
        self.assertEqual(
            DebtSettlementAllocation.objects.filter(wallet_transaction=self.txn).count(),
            1,
        )
        self.assertEqual(
            DebtSettlementAllocation.objects.get(wallet_transaction=self.txn).sale_id,
            self.right_sale.id,
        )
        self.assertNotIn(WRONG_PHONE, self.txn.notes)
        self.assertNotIn(RIGHT_PHONE, self.txn.notes)

    def test_move_sales_keeps_the_same_sale_paid_on_the_new_customer(self):
        """The sale and its debt row follow the repayment."""
        transfer_debt_settlement_customer(
            txn_id=self.txn.id,
            target_customer_id=self.right.id,
            user=self.admin,
            move_sales=True,
        )
        self.sale.refresh_from_db()
        self.txn.refresh_from_db()
        self.wrong.refresh_from_db()
        self.right.refresh_from_db()
        debt = CustomerWalletTransaction.objects.get(sale=self.sale, source_type='debt')
        self.assertEqual(self.sale.customer_id, self.right.id)
        self.assertEqual(self.sale.amount_paid, Decimal('100.00'))
        self.assertEqual(self.txn.customer_id, self.right.id)
        self.assertEqual(debt.customer_id, self.right.id)
        self.assertEqual(self.wrong.wallet_balance, Decimal('0.00'))
        self.assertEqual(self.right.wallet_balance, Decimal('-100.00'))

    def test_same_customer_and_inactive_target_are_refused(self):
        with self.assertRaises(Exception):
            transfer_debt_settlement_customer(
                txn_id=self.txn.id,
                target_customer_id=self.wrong.id,
                user=self.admin,
            )
        self.right.is_active = False
        self.right.save(update_fields=['is_active'])
        with self.assertRaises(Exception):
            transfer_debt_settlement_customer(
                txn_id=self.txn.id,
                target_customer_id=self.right.id,
                user=self.admin,
            )
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.amount_paid, Decimal('100.00'))

    def test_api_moves_repayment_without_leaking_phones(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        res = client.post(
            f'/api/sales/customers/wallet-settlements/{self.txn.id}/transfer-customer/',
            {
                'customer_id': self.right.id,
                'move_sales': False,
                'reason': 'Wrong customer',
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        body = str(res.data)
        self.assertNotIn(WRONG_PHONE, body)
        self.assertNotIn(RIGHT_PHONE, body)
        self.assertEqual(res.data['to_customer_id'], self.right.id)
        self.assertEqual(res.data['from_customer_name'], 'Wrong Shop')

    def test_sales_and_anonymous_cannot_move_it(self):
        url = f'/api/sales/customers/wallet-settlements/{self.txn.id}/transfer-customer/'
        payload = {'customer_id': self.right.id, 'move_sales': True}
        anon = APIClient()
        anon_res = anon.post(url, payload, format='json')
        self.assertEqual(anon_res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn(WRONG_PHONE, str(anon_res.data))

        sales = APIClient()
        sales.force_authenticate(user=self.sales)
        denied = sales.post(url, payload, format='json')
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(RIGHT_PHONE, str(denied.data))
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.customer_id, self.wrong.id)

    def test_feature_off_leaves_the_repayment_where_it_is(self):
        module, _ = ModuleSettings.objects.get_or_create(
            module_name='customers',
            defaults={'is_enabled': True},
        )
        was_enabled = module.is_enabled
        module.is_enabled = True
        module.save(update_fields=['is_enabled'])
        feature, _ = ModuleFeature.objects.get_or_create(
            module=module,
            feature_key='transfer_customer_on_collection',
            defaults={
                'feature_name': 'Move a repayment',
                'is_enabled': False,
            },
        )
        feature.is_enabled = False
        feature.save(update_fields=['is_enabled'])
        try:
            client = APIClient()
            client.force_authenticate(user=self.admin)
            res = client.post(
                f'/api/sales/customers/wallet-settlements/{self.txn.id}/transfer-customer/',
                {'customer_id': self.right.id},
                format='json',
            )
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
            self.assertNotIn(WRONG_PHONE, str(res.data))
            self.txn.refresh_from_db()
            self.assertEqual(self.txn.customer_id, self.wrong.id)
        finally:
            feature.is_enabled = True
            feature.save(update_fields=['is_enabled'])
            module.is_enabled = was_enabled
            module.save(update_fields=['is_enabled'])

    def test_eight_moves_keep_one_paid_sale(self):
        """Stress: moving the sale back and forth does not double the payment."""
        customers = [self.wrong, self.right]
        for step in range(8):
            target = customers[(step + 1) % 2]
            transfer_debt_settlement_customer(
                txn_id=self.txn.id,
                target_customer_id=target.id,
                user=self.admin,
                move_sales=True,
            )
        self.sale.refresh_from_db()
        self.txn.refresh_from_db()
        self.assertEqual(self.sale.customer_id, self.wrong.id)
        self.assertEqual(self.txn.customer_id, self.wrong.id)
        self.assertEqual(self.sale.amount_paid, Decimal('100.00'))
        self.assertEqual(
            DebtSettlementAllocation.objects.filter(wallet_transaction=self.txn).count(),
            1,
        )
        self.assertEqual(
            CustomerWalletTransaction.objects.filter(
                sale=self.sale, source_type='debt'
            ).count(),
            1,
        )
