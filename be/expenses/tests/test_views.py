"""Expense API tests."""

from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from expenses.models import Expense, ExpenseCategory
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase, SuperAdminAPITestCase


class ExpenseViewsTestCase(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cat = ExpenseCategory.objects.create(name='Utilities', is_active=True)

    def test_manager_can_create_but_not_approve_expense(self):
        create = self.client.post(
            '/api/expenses/',
            {
                'category': self.cat.id,
                'description': 'Electricity',
                'amount': '450.00',
                'expense_date': timezone.now().date().isoformat(),
                'payment_method': 'mpesa',
                'status': 'pending',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        expense_id = create.data['id']
        approve = self.client.post(f'/api/expenses/{expense_id}/approve/')
        self.assertEqual(approve.status_code, status.HTTP_403_FORBIDDEN)


class ExpenseApproveSuperAdminTests(SuperAdminAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cat = ExpenseCategory.objects.create(name='Ops', is_active=True)

    def test_super_admin_can_approve_expense(self):
        create = self.client.post(
            '/api/expenses/',
            {
                'category': self.cat.id,
                'description': 'Rent',
                'amount': '1200.00',
                'expense_date': timezone.now().date().isoformat(),
                'payment_method': 'cash',
                'status': 'pending',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        expense_id = create.data['id']
        approve = self.client.post(f'/api/expenses/{expense_id}/approve/')
        self.assertEqual(approve.status_code, status.HTTP_200_OK)
        self.assertEqual(approve.data['status'], 'approved')

    def test_statistics_endpoint(self):
        Expense.objects.create(
            category=self.cat,
            description='Water',
            amount=Decimal('100.00'),
            expense_date=timezone.now().date(),
            status='approved',
            created_by=self.manager_user,
        )
        response = self.client.get('/api/expenses/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_expenses', response.data)


class ExpensePermissionsTestCase(SalesAPITestCase):
    def test_sales_cannot_create_expense(self):
        cat = ExpenseCategory.objects.create(name='X')
        response = self.client.post(
            '/api/expenses/',
            {
                'category': cat.id,
                'description': 'Nope',
                'amount': '10.00',
                'expense_date': timezone.now().date().isoformat(),
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
