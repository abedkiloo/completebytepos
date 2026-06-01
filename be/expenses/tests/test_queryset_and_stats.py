"""Extended expense queryset, statistics, and API coverage."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from expenses.models import Expense, ExpenseCategory
from expenses.services import ExpenseCategoryService, ExpenseService
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class ExpenseQuerysetTests(TestCase):
    def setUp(self):
        self.service = ExpenseService()
        self.cat_a = ExpenseCategory.objects.create(name='Ops', is_active=True)
        self.cat_b = ExpenseCategory.objects.create(name='Travel', is_active=True)
        today = timezone.now().date()
        Expense.objects.create(
            category=self.cat_a,
            description='Pending item',
            amount=Decimal('50.00'),
            expense_date=today,
            status='pending',
            payment_method='cash',
        )
        Expense.objects.create(
            category=self.cat_a,
            description='Approved ops',
            amount=Decimal('200.00'),
            expense_date=today,
            status='approved',
            payment_method='mpesa',
        )
        Expense.objects.create(
            category=self.cat_b,
            description='Old travel',
            amount=Decimal('75.00'),
            expense_date=today - timedelta(days=40),
            status='approved',
            payment_method='bank',
        )

    def test_build_queryset_filters_status_and_category(self):
        qs = self.service.build_queryset(
            {'status': 'approved', 'category': str(self.cat_a.id)}
        )
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().description, 'Approved ops')

    def test_build_queryset_invalid_category_returns_empty(self):
        qs = self.service.build_queryset({'category': 'not-a-number'})
        self.assertEqual(qs.count(), 0)

    def test_build_queryset_date_range(self):
        today = timezone.now().date()
        qs = self.service.build_queryset(
            {
                'date_from': (today - timedelta(days=7)).isoformat(),
                'date_to': today.isoformat(),
            }
        )
        self.assertEqual(qs.count(), 2)

    def test_statistics_count_only_approved_in_total(self):
        stats = self.service.get_expense_statistics()
        self.assertEqual(stats['total_expenses'], 275.0)
        self.assertGreaterEqual(stats['month_expenses'], 200.0)
        self.assertTrue(any(row['category__name'] == 'Ops' for row in stats['by_category']))

    def test_category_service_active_filter(self):
        ExpenseCategory.objects.create(name='Retired', is_active=False)
        qs = ExpenseCategoryService().build_queryset({'is_active': 'true'})
        names = list(qs.values_list('name', flat=True))
        self.assertIn('Ops', names)
        self.assertNotIn('Retired', names)


class ExpenseAPIExtendedTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cat = ExpenseCategory.objects.create(name='Utilities', is_active=True)

    def test_list_filter_by_status(self):
        Expense.objects.create(
            category=self.cat,
            description='Pending',
            amount=Decimal('10.00'),
            expense_date=timezone.now().date(),
            status='pending',
            created_by=self.manager_user,
        )
        response = self.client.get('/api/expenses/?status=approved')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for row in response.data.get('results', response.data):
            self.assertEqual(row['status'], 'approved')

    def test_double_approve_returns_400(self):
        create = self.client.post(
            '/api/expenses/',
            {
                'category': self.cat.id,
                'description': 'Once',
                'amount': '25.00',
                'expense_date': timezone.now().date().isoformat(),
                'payment_method': 'cash',
                'status': 'pending',
            },
            format='json',
        )
        expense_id = create.data['id']
        self.client.post(f'/api/expenses/{expense_id}/approve/')
        again = self.client.post(f'/api/expenses/{expense_id}/approve/')
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)

    def test_category_list_and_create(self):
        list_resp = self.client.get('/api/expenses/categories/?is_active=true')
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        create = self.client.post(
            '/api/expenses/categories/',
            {'name': 'Maintenance', 'is_active': True},
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)


class ExpenseTransferPermissionsTestCase(SalesAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from settings.models import ModuleSettings
        ModuleSettings.objects.update_or_create(
            module_name='expenses',
            defaults={'description': 'expenses', 'is_enabled': True},
        )

    def test_sales_cannot_list_expenses(self):
        response = self.client.get('/api/expenses/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
