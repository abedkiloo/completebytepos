"""Expense service unit tests."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
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
