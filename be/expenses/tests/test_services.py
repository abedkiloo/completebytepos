"""Expense service unit tests."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from expenses.models import Expense, ExpenseCategory
from expenses.services import ExpenseCategoryService, ExpenseService


class ExpenseServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='exp_user', password='x')
        self.cat = ExpenseCategory.objects.create(name='Rent', is_active=True)
        self.service = ExpenseService()

    def test_approve_expense(self):
        expense = Expense.objects.create(
            category=self.cat,
            description='Office rent',
            amount=Decimal('1000.00'),
            expense_date=timezone.now().date(),
            status='pending',
            created_by=self.user,
        )
        approved = self.service.approve_expense(expense, self.user)
        self.assertEqual(approved.status, 'approved')
        self.assertEqual(approved.approved_by, self.user)

    def test_approve_already_approved_raises(self):
        expense = Expense.objects.create(
            category=self.cat,
            description='Paid',
            amount=Decimal('50.00'),
            expense_date=timezone.now().date(),
            status='approved',
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            self.service.approve_expense(expense, self.user)

    def test_statistics_include_approved(self):
        Expense.objects.create(
            category=self.cat,
            description='A',
            amount=Decimal('200.00'),
            expense_date=timezone.now().date(),
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
            expense_date=timezone.now().date(),
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
        today = timezone.now().date()
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
            expense_date=timezone.now().date(),
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

    def test_approve_journal_failure_is_non_fatal(self):
        expense = Expense.objects.create(
            category=self.cat,
            description='Journal fail',
            amount=Decimal('10.00'),
            expense_date=timezone.now().date(),
            status='pending',
            created_by=self.user,
        )
        with patch(
            'accounting.services.create_expense_journal_entry',
            side_effect=RuntimeError('ledger offline'),
        ):
            approved = self.service.approve_expense(expense, self.user)
        self.assertEqual(approved.status, 'approved')

    def test_statistics_with_branch_and_date_range(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, _ = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='STX'
        )
        today = timezone.now().date()
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
            expense_date=timezone.now().date(),
            status='pending',
            created_by=self.user,
        )
        stats = self.service.get_expense_statistics()
        self.assertLess(stats['total_expenses'], 999.0)
        self.assertTrue(any(row['status'] == 'pending' for row in stats['by_status']))
