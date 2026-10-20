"""Focused coverage for expenses views/services edge paths."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework import status

from expenses.models import Expense, ExpenseCategory
from expenses.serializers import ExpenseListSerializer
from expenses.services import ExpenseCategoryService, ExpenseService
from expenses.views import CanUpdateExpense, _user_has_expenses_perm
from utils.tests.api_test_base import SuperAdminAPITestCase


class ExpenseServiceFilterGapsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('exp_gap', password='x')
        self.cat = ExpenseCategory.objects.create(
            name='Travel', description='Trips', is_active=True,
        )
        self.expense = Expense.objects.create(
            category=self.cat,
            description='Taxi',
            amount=Decimal('30.00'),
            expense_date=timezone.localdate(),
            status='pending',
            created_by=self.user,
            payment_method='cash',
        )
        self.svc = ExpenseService()
        self.cat_svc = ExpenseCategoryService()

    def test_category_search_and_invalid_filters(self):
        qs = self.cat_svc.build_queryset({'search': 'Trav', 'is_active': 'true'})
        self.assertEqual(qs.count(), 1)

        none = self.svc.build_queryset({'branch_id': 'bad', 'show_all': 'false'})
        with patch('expenses.services.is_branch_support_enabled', return_value=True):
            none = self.svc.build_queryset({'branch_id': 'bad', 'show_all': 'false'})
            self.assertEqual(none.count(), 0)
            ok = self.svc.build_queryset({
                'branch_id': '1',
                'show_all': 'false',
                'category': 'not-int',
            })
            self.assertEqual(ok.count(), 0)

        filtered = self.svc.build_queryset({
            'approved_by': 'nope',
            'created_by': 'nope',
            'category': self.cat.id,
            'status': 'pending',
        })
        self.assertEqual(filtered.count(), 1)

    def test_void_and_resubmit_errors(self):
        with self.assertRaises(Exception):
            self.svc.void_expense(self.expense, reason='', user=self.user)

        self.expense.status = 'weird'
        self.expense.save(update_fields=['status'])
        with self.assertRaises(Exception):
            self.svc.void_expense(self.expense, reason='x', user=self.user)

        self.expense.status = 'rejected'
        self.expense.save(update_fields=['status'])
        other = User.objects.create_user('exp_other', password='x')
        with self.assertRaises(Exception):
            self.svc.resubmit_expense(self.expense, other)

    def test_list_serializer_without_category(self):
        self.expense.category = None
        self.expense.save(update_fields=['category'])
        data = ExpenseListSerializer(self.expense).data
        self.assertTrue(data['category_include_in_trading_profit'])


class ExpenseViewErrorPathsTests(SuperAdminAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cat = ExpenseCategory.objects.create(name='OpsGap', is_active=True)

    def test_reject_void_resubmit_error_responses(self):
        pending = Expense.objects.create(
            category=self.cat,
            description='Needs reason',
            amount=Decimal('12.00'),
            expense_date=timezone.localdate(),
            status='pending',
            created_by=self.admin,
            payment_method='cash',
        )
        reject = self.client.post(
            f'/api/expenses/{pending.id}/reject/',
            {},
            format='json',
        )
        self.assertEqual(reject.status_code, status.HTTP_400_BAD_REQUEST)

        void = self.client.post(
            f'/api/expenses/{pending.id}/void/',
            {},
            format='json',
        )
        self.assertEqual(void.status_code, status.HTTP_400_BAD_REQUEST)

        approved = Expense.objects.create(
            category=self.cat,
            description='Already done',
            amount=Decimal('12.00'),
            expense_date=timezone.localdate(),
            status='approved',
            created_by=self.admin,
            payment_method='cash',
        )
        resubmit = self.client.post(f'/api/expenses/{approved.id}/resubmit/')
        self.assertEqual(resubmit.status_code, status.HTTP_400_BAD_REQUEST)

        # category search query param hits view filter
        cats = self.client.get('/api/expenses/categories/', {'search': 'Ops', 'is_active': 'true'})
        self.assertEqual(cats.status_code, status.HTTP_200_OK)

    def test_permission_helpers(self):
        self.assertFalse(_user_has_expenses_perm(None, 'update'))
        self.assertFalse(_user_has_expenses_perm(AnonymousUser(), 'update'))
        self.assertTrue(_user_has_expenses_perm(self.admin, 'update'))

        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.admin
        view = type('V', (), {'action': 'update', 'get_object': lambda self: None})()
        perm = CanUpdateExpense()
        # Has expenses.update via superadmin
        expense = Expense.objects.create(
            category=self.cat,
            description='Own',
            amount=Decimal('1.00'),
            expense_date=timezone.localdate(),
            status='pending',
            created_by=self.admin,
            payment_method='cash',
        )
        view.get_object = lambda: expense
        self.assertTrue(perm.has_permission(request, view))
