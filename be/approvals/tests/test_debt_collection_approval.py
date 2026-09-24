"""Sales debt collections queue for manager/admin approval."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SUPER_ADMIN, ensure_permissions
from approvals.apply import apply_pending_change
from approvals.models import PendingChange
from approvals.permissions import user_can_check
from approvals.registry import ACTION_DEBT_COLLECTION, CHECKER_MODULE_BY_ACTION
from sales.debt_collection_approval import (
    collection_reason,
    queue_debt_collection,
)
from sales.models import Customer, CustomerWalletTransaction
from settings.test_utils import disable_maker_checker
from utils.tests.api_test_base import SalesAPITestCase


class DebtCollectionHelperTests(TestCase):
    def test_collection_reason_uses_notes_or_method(self):
        self.assertEqual(
            collection_reason(amount=Decimal('50.00'), payment_method='cash', notes='  Field visit  '),
            'Field visit',
        )
        self.assertEqual(
            collection_reason(amount=Decimal('50.00'), payment_method='mpesa'),
            'Debt collection of 50.00 via M-PESA',
        )
        self.assertEqual(
            collection_reason(amount=Decimal('10'), payment_method='mpesa'),
            'Debt collection of 10 via M-PESA',
        )

    def test_checker_module_is_debt_management(self):
        self.assertEqual(CHECKER_MODULE_BY_ACTION[ACTION_DEBT_COLLECTION], 'debt_management')


class DebtCollectionApprovalAPITests(SalesAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        disable_maker_checker()
        ensure_permissions()
        cls.manager_user = User.objects.create_user('debt_mgr', password='x')
        cls.manager_role = Role.objects.get(name=ROLE_MANAGER)
        UserProfile.objects.create(
            user=cls.manager_user,
            role='manager',
            custom_role=cls.manager_role,
            is_active=True,
        )
        cls.customer = Customer.objects.create(
            name='Queued Debtor',
            phone='0711000000',
            wallet_balance=Decimal('-250.00'),
            is_active=True,
        )

    def _manager_client(self):
        client = self.client.__class__()
        token = RefreshToken.for_user(self.manager_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def _admin_client(self):
        admin = User.objects.create_superuser('debt_admin', email='da@test.com', password='x')
        UserProfile.objects.create(
            user=admin,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(admin)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def _collect(self, client, amount='100.00', **extra):
        payload = {'amount': amount, 'payment_method': 'cash', **extra}
        return client.post(
            f'/api/sales/customers/{self.customer.id}/receive-wallet-payment/',
            payload,
            format='json',
        )

    def test_sales_queues_collection_without_changing_wallet(self):
        resp = self._collect(self.client)
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.assertIn('pending_change', resp.data)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('-250.00'))
        self.assertFalse(
            CustomerWalletTransaction.objects.filter(customer=self.customer).exists()
        )
        change = PendingChange.objects.get(action_type=ACTION_DEBT_COLLECTION)
        self.assertEqual(change.status, PendingChange.STATUS_PENDING)
        self.assertEqual(change.made_by_id, self.sales_user.id)

    def test_duplicate_pending_collection_blocked(self):
        first = self._collect(self.client)
        self.assertEqual(first.status_code, status.HTTP_202_ACCEPTED, first.data)
        second = self._collect(self.client, amount='40.00')
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already awaiting', str(second.data))

    def test_sales_cannot_approve_own_collection(self):
        queued = self._collect(self.client)
        self.assertEqual(queued.status_code, status.HTTP_202_ACCEPTED, queued.data)
        change = PendingChange.objects.get(action_type=ACTION_DEBT_COLLECTION)
        deny = self.client.post(f'/api/approvals/pending-changes/{change.id}/approve/')
        self.assertIn(deny.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN))

    def test_manager_approval_credits_wallet_as_sales_collector(self):
        queued = self._collect(self.client, amount='100.00', notes='Shop visit')
        self.assertEqual(queued.status_code, status.HTTP_202_ACCEPTED, queued.data)
        change = PendingChange.objects.get(action_type=ACTION_DEBT_COLLECTION)

        approved = self._manager_client().post(
            f'/api/approvals/pending-changes/{change.id}/approve/'
        )
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.data)

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('-150.00'))
        txn = CustomerWalletTransaction.objects.get(
            customer=self.customer, source_type='debt_settlement'
        )
        self.assertEqual(txn.amount, Decimal('100.00'))
        self.assertEqual(txn.created_by_id, self.sales_user.id)

    def test_manager_with_approve_records_payment_live(self):
        resp = self._collect(self._manager_client(), amount='50.00')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('-200.00'))
        self.assertFalse(
            PendingChange.objects.filter(
                action_type=ACTION_DEBT_COLLECTION,
                status=PendingChange.STATUS_PENDING,
            ).exists()
        )

    def test_staff_without_approve_cannot_check(self):
        staff = User.objects.create_user('debt_staff', password='x', is_staff=True)
        UserProfile.objects.create(
            user=staff,
            role='cashier',
            custom_role=self.sales_role,
            is_active=True,
        )
        self.assertFalse(user_can_check(staff, ACTION_DEBT_COLLECTION))
        self.assertTrue(user_can_check(self.manager_user, ACTION_DEBT_COLLECTION))
        self.assertFalse(user_can_check(self.sales_user, ACTION_DEBT_COLLECTION))

    def test_manager_cannot_self_approve_queued_collection(self):
        approve_perm = Permission.objects.get(module='debt_management', action='approve')
        self.manager_role.permissions.remove(approve_perm)
        self.manager_user.profile.refresh_from_db()
        self.assertFalse(user_can_check(self.manager_user, ACTION_DEBT_COLLECTION))

        queued = self._collect(self._manager_client())
        self.assertEqual(queued.status_code, status.HTTP_202_ACCEPTED, queued.data)
        change = PendingChange.objects.get(action_type=ACTION_DEBT_COLLECTION)

        self.manager_role.permissions.add(approve_perm)
        deny = self._manager_client().post(
            f'/api/approvals/pending-changes/{change.id}/approve/'
        )
        self.assertIn(deny.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN))

        approved = self._admin_client().post(
            f'/api/approvals/pending-changes/{change.id}/approve/'
        )
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.data)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal('-150.00'))

    def test_queue_helper_rejects_zero_and_duplicate(self):
        factory = RequestFactory()
        request = factory.post('/')
        request.user = self.sales_user
        with self.assertRaises(ValidationError):
            queue_debt_collection(
                request,
                self.customer,
                amount=Decimal('0'),
                payment_method='cash',
            )
        pending = queue_debt_collection(
            request,
            self.customer,
            amount=Decimal('10.00'),
            payment_method='cash',
            notes='Shop visit',
        )
        self.assertEqual(pending.action_type, ACTION_DEBT_COLLECTION)
        self.assertEqual(pending.reason, 'Shop visit')
        with self.assertRaises(ValidationError):
            queue_debt_collection(
                request,
                self.customer,
                amount=Decimal('5.00'),
                payment_method='cash',
            )

    def test_apply_rejects_missing_customer_and_bad_amount(self):
        change = PendingChange.objects.create(
            action_type=ACTION_DEBT_COLLECTION,
            entity_type='sales.Customer',
            entity_id='999999',
            entity_repr='gone',
            reason='test',
            apply_payload={'amount': '10.00', 'payment_method': 'cash'},
            made_by=self.sales_user,
        )
        with self.assertRaises(ValidationError):
            apply_pending_change(change)

        change.entity_id = str(self.customer.pk)
        change.apply_payload = {'amount': 'not-a-number'}
        change.save()
        with self.assertRaises(ValidationError):
            apply_pending_change(change)

        change.apply_payload = {'amount': '-1'}
        change.save()
        with self.assertRaises(ValidationError):
            apply_pending_change(change)

    def test_approve_rejected_if_customer_deleted(self):
        queued = self._collect(self.client)
        self.assertEqual(queued.status_code, status.HTTP_202_ACCEPTED, queued.data)
        change = PendingChange.objects.get(action_type=ACTION_DEBT_COLLECTION)
        self.customer.delete()
        denied = self._manager_client().post(
            f'/api/approvals/pending-changes/{change.id}/approve/'
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)

    def test_approve_rejected_if_amount_invalid(self):
        queued = self._collect(self.client)
        self.assertEqual(queued.status_code, status.HTTP_202_ACCEPTED, queued.data)
        change = PendingChange.objects.get(action_type=ACTION_DEBT_COLLECTION)
        change.apply_payload = {'amount': '0'}
        change.save(update_fields=['apply_payload'])
        denied = self._manager_client().post(
            f'/api/approvals/pending-changes/{change.id}/approve/'
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)
        change.apply_payload = {'amount': 'nope'}
        change.save(update_fields=['apply_payload'])
        denied = self._manager_client().post(
            f'/api/approvals/pending-changes/{change.id}/approve/'
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)
