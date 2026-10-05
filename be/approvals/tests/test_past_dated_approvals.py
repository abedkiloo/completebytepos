"""Managers approve today's items; anything dated before today needs an admin. Expenses always need an admin."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.test import TestCase
from django.utils import timezone
from accounts.models import Role, UserProfile
from accounts.role_definitions import (
    ROLE_MANAGER,
    ROLE_SALES,
    ROLE_SUPER_ADMIN,
    ensure_permissions,
    sync_default_roles,
)
from approvals.models import PendingChange
from approvals.permissions import (
    PAST_DATED_ADMIN_ONLY_MESSAGE,
    change_is_past_dated,
    is_past_dated,
    user_may_approve_change,
    user_may_approve_past_items,
)
from approvals.registry import ACTION_DEBT_COLLECTION, ACTION_SALE_BACKFILL
from approvals.serializers import PendingChangeSerializer
from approvals.service import reject_change
from expenses.models import Expense
from expenses.services import ExpenseService
from settings.test_utils import disable_maker_checker


class PastDatedApprovalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        disable_maker_checker()
        cls.manager = User.objects.create_user('past_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.admin = User.objects.create_user('past_admin', password='x')
        UserProfile.objects.create(
            user=cls.admin,
            role='super_admin',
            custom_role=roles[ROLE_SUPER_ADMIN],
            is_active=True,
        )
        cls.sales = User.objects.create_user('past_sales', password='x')
        UserProfile.objects.create(
            user=cls.sales, role='cashier', custom_role=roles[ROLE_SALES], is_active=True,
        )

    def _change(self, *, days_ago=0, action=ACTION_DEBT_COLLECTION, payload=None):
        change = PendingChange.objects.create(
            action_type=action,
            entity_type='sales.Customer',
            entity_id='1',
            reason='test',
            made_by=self.sales,
            apply_payload=payload or {},
        )
        if days_ago:
            PendingChange.objects.filter(pk=change.pk).update(
                made_at=timezone.now() - timedelta(days=days_ago),
            )
            change.refresh_from_db()
        return change

    def test_only_admins_may_approve_past_items(self):
        self.assertTrue(user_may_approve_past_items(self.admin))
        self.assertFalse(user_may_approve_past_items(self.manager))
        self.assertFalse(user_may_approve_past_items(self.sales))

    def test_is_past_dated_uses_earliest_date(self):
        today = timezone.localdate()
        self.assertFalse(is_past_dated(today))
        self.assertTrue(is_past_dated(today, today - timedelta(days=1)))
        self.assertFalse(is_past_dated(None))

    def test_manager_approves_todays_request(self):
        change = self._change()
        self.assertFalse(change_is_past_dated(change))
        self.assertTrue(user_may_approve_change(self.manager, change))

    def test_request_from_yesterday_is_admin_only(self):
        change = self._change(days_ago=1)
        self.assertTrue(change_is_past_dated(change))
        self.assertFalse(user_may_approve_change(self.manager, change))
        self.assertTrue(user_may_approve_change(self.admin, change))
        self.assertTrue(PendingChangeSerializer(change).data['past_dated'])

    def test_backfill_dated_yesterday_is_admin_only_even_if_raised_today(self):
        yesterday = (timezone.now() - timedelta(days=1)).isoformat()
        change = self._change(action=ACTION_SALE_BACKFILL, payload={'occurred_at': yesterday})
        self.assertTrue(change_is_past_dated(change))
        self.assertFalse(user_may_approve_change(self.manager, change))

    def test_manager_cannot_return_past_request(self):
        change = self._change(days_ago=2)
        with self.assertRaises(DjangoValidationError) as ctx:
            reject_change(change, self.manager, 'wrong amount')
        self.assertIn(PAST_DATED_ADMIN_ONLY_MESSAGE, str(ctx.exception))
        change.refresh_from_db()
        self.assertEqual(change.status, PendingChange.STATUS_PENDING)

    def _expense(self, day):
        return Expense.objects.create(
            amount=Decimal('100.00'),
            description='Fuel',
            expense_date=day,
            created_by=self.sales,
        )

    def test_expenses_need_an_admin_even_when_dated_today(self):
        expense = self._expense(timezone.localdate())
        with self.assertRaises(PermissionDenied):
            ExpenseService().approve_expense(expense, self.manager)
        ExpenseService().approve_expense(expense, self.admin)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'approved')

    def test_past_expense_needs_admin(self):
        expense = self._expense(timezone.localdate() - timedelta(days=1))
        with self.assertRaises(PermissionDenied):
            ExpenseService().approve_expense(expense, self.manager)
        ExpenseService().approve_expense(expense, self.admin)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'approved')
