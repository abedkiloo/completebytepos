"""Move one completed sale, or one repayment, onto the right customer."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import UserProfile
from accounts.role_definitions import ROLE_SALES, ensure_permissions, sync_default_roles
from sales.debt_settlement_correction import transfer_debt_settlement_customer
from sales.models import Customer, CustomerWalletTransaction, Sale
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
