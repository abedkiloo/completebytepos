"""
Security tests for payment / wallet settlement detail.

Covers authn, authz (debt_management.view), IDOR via Field Sales visibility,
unsafe HTTP methods, correction privilege, and error response non-leakage.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Permission, UserProfile
from accounts.role_definitions import (
    ROLE_FIELD_AGENT,
    ROLE_MANAGER,
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from sales.models import Customer, CustomerWalletTransaction
from sales.payments_trail import get_wallet_settlement_detail
from sales.services import CustomerService
from utils.tests.api_test_base import ManagerAPITestCase, SuperAdminAPITestCase


def _auth_client(user) -> APIClient:
    """
    Build an authenticated APIClient for ``user``.

    Args:
        user: Django auth user (must have a primary key).

    Returns:
        APIClient with ``force_authenticate`` set; empty if user is None.
    """
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


def _assert_no_payment_leak(response) -> None:
    """
    Assert error bodies do not leak settlement / payer / proof fields.

    Args:
        response: DRF Response-like with ``.data``.

    Raises:
        AssertionError: When sensitive keys appear in the error payload.
    """
    data = response.data
    if not isinstance(data, dict):
        return
    forbidden_keys = {
        'payer_name',
        'payer_phone',
        'receipt_image_url',
        'reference',
        'mpesa_destination',
        'paid_towards',
        'amount',
        'customer_phone',
    }
    leaked = forbidden_keys.intersection(data.keys())
    assert not leaked, f'Error response leaked fields: {sorted(leaked)} → {data}'


class PaymentDetailSecurityTests(SuperAdminAPITestCase):
    """Authn / authz / IDOR for GET wallet settlement detail."""

    def setUp(self):
        super().setUp()
        ensure_permissions()
        roles = sync_default_roles(created_by=self.admin)
        self.field_role = roles[ROLE_FIELD_AGENT]
        self.manager_role = roles[ROLE_MANAGER]
        self.sales_role = roles[ROLE_SALES]

        self.agent = User.objects.create_user('pd_sec_agent', password='x')
        UserProfile.objects.create(
            user=self.agent,
            role='cashier',
            custom_role=self.field_role,
            is_active=True,
        )
        self.other_agent = User.objects.create_user('pd_sec_other', password='x')
        UserProfile.objects.create(
            user=self.other_agent,
            role='cashier',
            custom_role=self.field_role,
            is_active=True,
        )
        self.sales = User.objects.create_user('pd_sec_sales', password='x')
        UserProfile.objects.create(
            user=self.sales,
            role='cashier',
            custom_role=self.sales_role,
            is_active=True,
        )
        self.manager = User.objects.create_user('pd_sec_mgr', password='x')
        UserProfile.objects.create(
            user=self.manager,
            role='manager',
            custom_role=self.manager_role,
            is_active=True,
        )

        self.mine = Customer.objects.create(
            name='Sec Own Duka',
            phone='0711888001',
            wallet_balance=Decimal('-200.00'),
            is_active=True,
            created_by=self.agent,
        )
        self.theirs = Customer.objects.create(
            name='Sec Other Duka',
            phone='0711888002',
            wallet_balance=Decimal('-200.00'),
            is_active=True,
            created_by=self.other_agent,
        )
        CustomerWalletTransaction.objects.create(
            customer=self.mine,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('200.00'),
            balance_after=Decimal('-200.00'),
            created_by=self.manager,
        )
        CustomerWalletTransaction.objects.create(
            customer=self.theirs,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('200.00'),
            balance_after=Decimal('-200.00'),
            created_by=self.manager,
        )
        self.own_txn = CustomerService().record_wallet_payment(
            self.mine,
            Decimal('40.00'),
            payment_method='mpesa',
            reference='QHXSEC001A1',
            user=self.manager,
            payer_name='Secret Payer',
            payer_phone='0700111000',
            mpesa_destination='till',
        )
        self.other_txn = CustomerService().record_wallet_payment(
            self.theirs,
            Decimal('40.00'),
            payment_method='mpesa',
            reference='QHXSEC002B2',
            user=self.manager,
            payer_name='Other Secret',
            payer_phone='0700222000',
            mpesa_destination='bank',
        )

    def _detail_url(self, txn_id: int) -> str:
        return f'/api/sales/customers/wallet-settlements/{txn_id}/'

    def _amount_url(self, txn_id: int) -> str:
        return f'/api/sales/customers/wallet-settlements/{txn_id}/amount/'

    def test_unauthenticated_get_denied(self):
        res = APIClient().get(self._detail_url(self.own_txn.id))
        self.assertIn(
            res.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        _assert_no_payment_leak(res)

    def test_field_agent_without_debt_perm_denied(self):
        res = _auth_client(self.agent).get(self._detail_url(self.own_txn.id))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, res.data)
        _assert_no_payment_leak(res)

    def test_field_agent_with_view_can_open_own_settlement(self):
        view_perm = Permission.objects.get(module='debt_management', action='view')
        self.field_role.permissions.add(view_perm)
        res = _auth_client(self.agent).get(self._detail_url(self.own_txn.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data['id'], self.own_txn.id)
        self.assertEqual(res.data['customer_id'], self.mine.id)

    def test_field_agent_idor_other_customer_settlement_forbidden(self):
        """IDOR: debt.view alone must not expose another agent's customer payment."""
        view_perm = Permission.objects.get(module='debt_management', action='view')
        self.field_role.permissions.add(view_perm)
        res = _auth_client(self.agent).get(self._detail_url(self.other_txn.id))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, res.data)
        _assert_no_payment_leak(res)
        self.assertNotIn('Other Secret', str(res.data))
        self.assertNotIn('QHXSEC002B2', str(res.data))

    def test_helper_raises_permission_error_for_scoped_user(self):
        view_perm = Permission.objects.get(module='debt_management', action='view')
        self.field_role.permissions.add(view_perm)
        with self.assertRaises(PermissionError):
            get_wallet_settlement_detail(self.other_txn.id, user=self.agent)

    def test_unsafe_methods_not_allowed_on_detail(self):
        client = _auth_client(self.manager)
        url = self._detail_url(self.own_txn.id)
        for method in ('post', 'put', 'patch', 'delete'):
            res = getattr(client, method)(url, {}, format='json')
            self.assertEqual(
                res.status_code,
                status.HTTP_405_METHOD_NOT_ALLOWED,
                f'{method.upper()} → {res.status_code} {getattr(res, "data", None)}',
            )

    def test_correct_amount_requires_correct_permission(self):
        payload = {'amount': '10.00', 'reason': 'probe'}
        for user in (None, self.sales, self.manager, self.agent):
            res = _auth_client(user).patch(
                self._amount_url(self.own_txn.id),
                payload,
                format='json',
            )
            self.assertIn(
                res.status_code,
                (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
                f'user={getattr(user, "username", None)} → {res.status_code}',
            )
            _assert_no_payment_leak(res)

    def test_missing_settlement_404_does_not_leak(self):
        res = _auth_client(self.manager).get(self._detail_url(9_999_999))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        _assert_no_payment_leak(res)

    def test_non_settlement_txn_404_does_not_leak(self):
        debt_row = CustomerWalletTransaction.objects.filter(
            customer=self.mine,
            source_type='debt',
        ).first()
        self.assertIsNotNone(debt_row)
        res = _auth_client(self.manager).get(self._detail_url(debt_row.id))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        _assert_no_payment_leak(res)


class PaymentDetailSecurityStressTests(ManagerAPITestCase):
    """Stress unauthorized probes against settlement detail."""

    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            name='Sec Stress Cust',
            phone='0711888999',
            wallet_balance=Decimal('-500.00'),
            is_active=True,
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('500.00'),
            balance_after=Decimal('-500.00'),
            created_by=self.manager_user,
        )
        self.txn = CustomerService().record_wallet_payment(
            self.customer,
            Decimal('15.00'),
            payment_method='cash',
            user=self.manager_user,
        )

    def test_unauthenticated_burst_still_denied(self):
        client = APIClient()
        url = f'/api/sales/customers/wallet-settlements/{self.txn.id}/'
        codes = []
        for _ in range(80):
            res = client.get(url)
            codes.append(res.status_code)
            _assert_no_payment_leak(res)
        self.assertTrue(
            all(c in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN) for c in codes)
        )
        self.assertEqual(len(codes), 80)
