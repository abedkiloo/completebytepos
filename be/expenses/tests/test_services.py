"""Expense service unit tests."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from expenses.models import Expense, ExpenseCategory
from expenses.services import ExpenseCategoryService, ExpenseService
from settings.models import StoreSettings
from settings.test_utils import disable_maker_checker


class ExpenseServiceTestCase(TestCase):
    def setUp(self):
        disable_maker_checker()
        self.user = User.objects.create_user(username='exp_user', password='x')
        self.cat = ExpenseCategory.objects.create(name='Rent', is_active=True)
        self.service = ExpenseService()
        self.admin = self._admin('exp_admin')

    def _admin(self, username):
        from accounts.models import UserProfile

        user = User.objects.create_user(username=username, password='x')
        UserProfile.objects.create(user=user, role='admin', is_active=True)
        return user

    def test_approve_expense(self):
        expense = Expense.objects.create(
            category=self.cat,
            description='Office rent',
            amount=Decimal('1000.00'),
            expense_date=timezone.localdate(),
            status='pending',
            created_by=self.user,
        )
        approved = self.service.approve_expense(expense, self.admin)
        self.assertEqual(approved.status, 'approved')
        self.assertEqual(approved.approved_by, self.admin)

    def test_reject_expense_notifies_requester(self):
        from daily_notes.models import DailyNote, DailyTask

        expense = Expense.objects.create(
            category=self.cat,
            description='Office rent',
            amount=Decimal('1000.00'),
            expense_date=timezone.localdate(),
            status='pending',
            created_by=self.user,
        )
        checker = self._admin('exp_rejector')
        rejected = self.service.reject_expense(expense, checker, 'Need receipt')
        self.assertEqual(rejected.status, 'rejected')
        self.assertIn('Need receipt', rejected.notes)
        note = DailyNote.objects.get(author=self.user)
        self.assertIn('expense', note.title)
        task = DailyTask.objects.get(assigned_to=self.user)
        self.assertFalse(task.is_done)
        queued = self.service.resubmit_expense(expense, self.user)
        self.assertEqual(queued.status, 'pending')

    def test_reject_expense_requires_reason_and_pending(self):
        expense = Expense.objects.create(
            category=self.cat,
            description='Fuel',
            amount=Decimal('80.00'),
            expense_date=timezone.localdate(),
            status='pending',
            created_by=self.user,
        )
        checker = self._admin('exp_rejector2')
        with self.assertRaises(ValidationError):
            self.service.reject_expense(expense, checker, '  ')
        expense.status = 'approved'
        expense.save(update_fields=['status'])
        with self.assertRaises(ValidationError):
            self.service.reject_expense(expense, checker, 'Too late')
        expense.status = 'rejected'
        expense.save(update_fields=['status'])
        other = User.objects.create_user(username='not_maker', password='x')
        with self.assertRaises(ValidationError):
            self.service.resubmit_expense(expense, other)

    def test_only_admins_approve_or_return_expenses(self):
        from django.core.exceptions import PermissionDenied

        from accounts.models import UserProfile
        from expenses.services import EXPENSE_ADMIN_ONLY_MESSAGE

        manager = User.objects.create_user(username='exp_manager', password='x')
        UserProfile.objects.create(user=manager, role='manager', is_active=True)
        for maker_checker in (True, False):
            store = StoreSettings.load()
            store.maker_checker_enabled = maker_checker
            store.save(update_fields=['maker_checker_enabled'])
            expense = Expense.objects.create(
                category=self.cat,
                description='Fuel',
                amount=Decimal('80.00'),
                expense_date=timezone.localdate(),
                status='pending',
                created_by=self.user,
            )
            for checker in (self.user, manager):
                with self.assertRaisesMessage(PermissionDenied, EXPENSE_ADMIN_ONLY_MESSAGE):
                    self.service.approve_expense(expense, checker)
                with self.assertRaisesMessage(PermissionDenied, EXPENSE_ADMIN_ONLY_MESSAGE):
                    self.service.reject_expense(expense, checker, 'No receipt')
            expense.refresh_from_db()
            self.assertEqual(expense.status, 'pending')
            approved = self.service.approve_expense(expense, self.admin)
            self.assertEqual(approved.status, 'approved')
        disable_maker_checker()

    def test_admin_may_approve_own_expense(self):
        expense = Expense.objects.create(
            category=self.cat, description='Admin fuel', amount=Decimal('20.00'),
            expense_date=timezone.localdate(), status='pending', created_by=self.admin,
        )
        self.assertEqual(self.service.approve_expense(expense, self.admin).status, 'approved')

    def test_only_pending_expenses_can_be_approved(self):
        for status in ('rejected', 'voided', 'paid'):
            expense = Expense.objects.create(
                category=self.cat, description=status, amount=Decimal('5.00'),
                expense_date=timezone.localdate(), status=status, created_by=self.user,
            )
            with self.assertRaisesMessage(ValidationError, 'Only pending expenses can be approved.'):
                self.service.approve_expense(expense, self.admin)

    def test_approve_already_approved_raises(self):
        expense = Expense.objects.create(
            category=self.cat,
            description='Paid',
            amount=Decimal('50.00'),
            expense_date=timezone.localdate(),
            status='approved',
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            self.service.approve_expense(expense, self.admin)

    def test_statistics_include_approved(self):
        Expense.objects.create(
            category=self.cat,
            description='A',
            amount=Decimal('200.00'),
            expense_date=timezone.localdate(),
            status='approved',
            created_by=self.user,
        )
        stats = self.service.get_expense_statistics()
        self.assertGreaterEqual(stats['total_expenses'], 200.0)

    def test_category_service_filter_active(self):
        ExpenseCategory.objects.create(name='Inactive', is_active=False)
        qs = ExpenseCategoryService().build_queryset({'is_active': True})
        self.assertFalse(qs.filter(name='Inactive').exists())

    def test_build_queryset_none_filters_defaults(self):
        self.assertGreaterEqual(self.service.build_queryset(None).count(), 0)

    def test_build_queryset_filters_category_status_and_payment(self):
        Expense.objects.create(
            category=self.cat,
            description='Pending bill',
            amount=Decimal('75.00'),
            expense_date=timezone.localdate(),
            status='pending',
            payment_method='cash',
            created_by=self.user,
        )
        qs = self.service.build_queryset({
            'category': self.cat.id,
            'status': 'pending',
            'payment_method': 'cash',
            'show_all': 'true',
        })
        self.assertEqual(qs.count(), 1)

    def test_build_queryset_invalid_category_returns_empty(self):
        qs = self.service.build_queryset({'category': 'bad', 'show_all': 'true'})
        self.assertEqual(qs.count(), 0)

    def test_build_queryset_branch_and_date_filters(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, branch_b = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='EXP'
        )
        today = timezone.localdate()
        Expense.objects.create(
            category=self.cat,
            description='Branch spend',
            amount=Decimal('40.00'),
            expense_date=today,
            status='approved',
            branch=branch_a,
            created_by=self.user,
        )
        qs = self.service.build_queryset({
            'branch_id': branch_a.id,
            'date_from': today,
            'date_to': today,
        })
        self.assertEqual(qs.count(), 1)
        other = self.service.build_queryset({'branch_id': branch_b.id})
        self.assertEqual(other.count(), 0)

    def test_category_service_no_filters_returns_all(self):
        qs = ExpenseCategoryService().build_queryset()
        self.assertGreaterEqual(qs.count(), 1)

    def test_category_service_is_active_string_filter(self):
        ExpenseCategory.objects.create(name='Off', is_active=False)
        qs = ExpenseCategoryService().build_queryset({'is_active': 'false'})
        self.assertFalse(qs.filter(name='Rent').exists())

    def test_category_service_is_active_true_string(self):
        qs = ExpenseCategoryService().build_queryset({'is_active': 'true'})
        self.assertTrue(qs.filter(name='Rent').exists())

    def test_build_queryset_payment_method_filter(self):
        Expense.objects.create(
            category=self.cat,
            description='Mpesa pay',
            amount=Decimal('30.00'),
            expense_date=timezone.localdate(),
            status='approved',
            payment_method='mpesa',
            created_by=self.user,
        )
        qs = self.service.build_queryset({'payment_method': 'mpesa'})
        self.assertEqual(qs.count(), 1)

    def test_build_queryset_resolves_branch_from_request(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, _ = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='REQ'
        )
        Expense.objects.create(
            category=self.cat,
            description='Session branch',
            amount=Decimal('15.00'),
            expense_date=timezone.localdate(),
            status='approved',
            branch=branch_a,
            created_by=self.user,
        )
        request = RequestFactory().get('/api/expenses/')
        with patch('expenses.services.get_current_branch', return_value=branch_a):
            qs = self.service.build_queryset({'show_all': 'false'}, request=request)
        self.assertEqual(qs.count(), 1)

    def test_build_queryset_invalid_branch_id_returns_empty(self):
        qs = self.service.build_queryset({'branch_id': 'not-int'})
        self.assertEqual(qs.count(), 0)

    def test_build_queryset_invalid_category_id_returns_empty(self):
        qs = self.service.build_queryset({'category': 'not-int'})
        self.assertEqual(qs.count(), 0)

    def test_approve_journal_failure_is_non_fatal(self):
        expense = Expense.objects.create(
            category=self.cat,
            description='Journal fail',
            amount=Decimal('10.00'),
            expense_date=timezone.localdate(),
            status='pending',
            created_by=self.user,
        )
        with patch(
            'accounting.services.create_expense_journal_entry',
            side_effect=RuntimeError('ledger offline'),
        ):
            approved = self.service.approve_expense(expense, self.admin)
        self.assertEqual(approved.status, 'approved')

    def test_statistics_with_branch_and_date_range(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, _ = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='STX'
        )
        today = timezone.localdate()
        Expense.objects.create(
            category=self.cat,
            description='Scoped',
            amount=Decimal('60.00'),
            expense_date=today,
            status='approved',
            branch=branch_a,
            created_by=self.user,
        )
        stats = self.service.get_expense_statistics(
            branch=branch_a,
            date_from=today,
            date_to=today,
        )
        self.assertGreaterEqual(stats['total_expenses'], 60.0)

    def test_statistics_pending_excluded_from_total(self):
        Expense.objects.create(
            category=self.cat,
            description='Waiting',
            amount=Decimal('999.00'),
            expense_date=timezone.localdate(),
            status='pending',
            created_by=self.user,
        )
        stats = self.service.get_expense_statistics()
        self.assertLess(stats['total_expenses'], 999.0)
        self.assertTrue(any(row['status'] == 'pending' for row in stats['by_status']))

    def test_void_approved_expense_reverses_journals(self):
        from accounting.models import Transaction
        from accounting.reversal import transaction_is_reversed

        expense = Expense.objects.create(
            category=self.cat,
            description='Wrong vendor',
            amount=Decimal('75.00'),
            expense_date=timezone.localdate(),
            status='pending',
            created_by=self.user,
        )
        self.service.approve_expense(expense, self.admin)
        txn = Transaction.objects.get(reference_type='expense', reference_id=expense.id)
        voided = self.service.void_expense(expense, reason='wrong vendor', user=self.user)
        self.assertEqual(voided.status, 'voided')
        self.assertIn('VOIDED', voided.notes)
        self.assertTrue(transaction_is_reversed(txn))
        with self.assertRaises(ValidationError):
            self.service.void_expense(voided, reason='again', user=self.user)

    def test_void_pending_requires_reason(self):
        expense = Expense.objects.create(
            category=self.cat,
            description='Draft',
            amount=Decimal('10.00'),
            expense_date=timezone.localdate(),
            status='pending',
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            self.service.void_expense(expense, reason='', user=self.user)
        voided = self.service.void_expense(expense, reason='never posted', user=self.user)
        self.assertEqual(voided.status, 'voided')
