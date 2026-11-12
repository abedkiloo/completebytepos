"""Admin-only correction of posted debt collection amounts."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, UserProfile
from accounts.role_definitions import (
    ROLE_MANAGER,
    ROLE_SALES,
    ROLE_SUPER_ADMIN,
    ensure_permissions,
    sync_default_roles,
)
from sales.debt_settlement_correction import correct_debt_settlement_amount
from sales.models import Customer, CustomerWalletTransaction, DebtSettlementAllocation, Sale
from sales.services import CustomerService
from utils.tests.api_test_base import SuperAdminAPITestCase


class DebtSettlementCorrectionTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        roles = sync_default_roles(created_by=self.admin)
        self.manager = User.objects.create_user('corr_mgr', password='x')
        UserProfile.objects.create(
            user=self.manager,
            role='manager',
            custom_role=roles[ROLE_MANAGER],
            is_active=True,
        )
        self.sales = User.objects.create_user('corr_sales', password='x')
        UserProfile.objects.create(
            user=self.sales,
            role='cashier',
            custom_role=roles[ROLE_SALES],
            is_active=True,
        )
        self.customer = Customer.objects.create(
            name='Corr Customer',
            phone='0711555000',
            wallet_balance=Decimal('-100.00'),
            is_active=True,
        )
        self.sale = Sale.objects.create(
            sale_number='CORR-SALE-1',
            status='completed',
            sale_type='pos',
            entry_source='pos',
            customer=self.customer,
            cashier=self.sales,
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
            amount_paid=Decimal('0.00'),
            payment_method='cash',
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('100.00'),
            balance_after=Decimal('-100.00'),
            sale=self.sale,
            created_by=self.sales,
        )
        self.txn = CustomerService().record_wallet_payment(
            customer=self.customer,
            amount=Decimal('100.00'),
            payment_method='cash',
            user=self.manager,
        )
        self.customer.refresh_from_db()
        self.sale.refresh_from_db()

    def test_wallet_settlement_detail_api(self):
        self.txn.payer_name = 'Payor'
        self.txn.payer_phone = '0700123456'
        self.txn.mpesa_destination = 'till'
        self.txn.payment_method = 'mpesa'
        self.txn.reference = 'QHX7K2L9M1'
        self.txn.save(
            update_fields=[
                'payer_name',
                'payer_phone',
                'mpesa_destination',
                'payment_method',
                'reference',
            ]
        )
        res = self.client.get(
            f'/api/sales/customers/wallet-settlements/{self.txn.id}/',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['kind'], 'debt_settlement')
        self.assertEqual(res.data['id'], self.txn.id)
        self.assertEqual(res.data['payer_name'], 'Payor')
        self.assertEqual(res.data['mpesa_destination'], 'till')
        self.assertEqual(res.data['reference'], 'QHX7K2L9M1')
        self.assertIn('paid_towards', res.data)

    def test_service_corrects_amount_and_reallocates(self):
        self.assertEqual(self.customer.wallet_balance, Decimal('0.00'))
        self.assertEqual(self.sale.amount_paid, Decimal('100.00'))
        self.assertTrue(
            DebtSettlementAllocation.objects.filter(wallet_transaction=self.txn).exists()
        )

        updated = correct_debt_settlement_amount(
            txn_id=self.txn.id,
            new_amount=Decimal('60.00'),
            user=self.admin,
            reason='Typo — was 60 cash',
        )
        self.customer.refresh_from_db()
        self.sale.refresh_from_db()
        self.assertEqual(updated.amount, Decimal('60.00'))
        self.assertEqual(self.customer.wallet_balance, Decimal('-40.00'))
        self.assertEqual(self.sale.amount_paid, Decimal('60.00'))
        alloc_total = sum(
            a.amount
            for a in DebtSettlementAllocation.objects.filter(wallet_transaction=updated)
        )
        self.assertEqual(alloc_total, Decimal('60.00'))

    def test_admin_api_patches_amount(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        res = client.patch(
            f'/api/sales/customers/wallet-settlements/{self.txn.id}/amount/',
            {'amount': '75.00', 'reason': 'Counted till again'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(Decimal(res.data['new_amount']), Decimal('75.00'))
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.amount, Decimal('75.00'))

    def test_manager_forbidden(self):
        client = APIClient()
        client.force_authenticate(user=self.manager)
        res = client.patch(
            f'/api/sales/customers/wallet-settlements/{self.txn.id}/amount/',
            {'amount': '50.00'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_forbidden(self):
        client = APIClient()
        client.force_authenticate(user=self.sales)
        res = client.patch(
            f'/api/sales/customers/wallet-settlements/{self.txn.id}/amount/',
            {'amount': '50.00'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_super_admin_role_has_correct_perm(self):
        sa = Role.objects.get(name=ROLE_SUPER_ADMIN)
        self.assertTrue(
            sa.permissions.filter(module='debt_management', action='correct').exists()
        )
        mgr = Role.objects.get(name=ROLE_MANAGER)
        self.assertFalse(
            mgr.permissions.filter(module='debt_management', action='correct').exists()
        )
