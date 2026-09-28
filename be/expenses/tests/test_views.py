"""Expense API tests."""

from datetime import timedelta
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

    def test_create_persists_past_occurred_date(self):
        occurred = timezone.localdate() - timedelta(days=9)
        create = self.client.post(
            '/api/expenses/',
            {
                'category': self.cat.id,
                'description': 'Shop rent last week',
                'amount': '8000.00',
                'expense_date': occurred.isoformat(),
                'payment_method': 'bank',
                'status': 'pending',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        self.assertEqual(create.data['expense_date'], occurred.isoformat())
        saved = Expense.objects.get(id=create.data['id'])
        self.assertEqual(saved.expense_date, occurred)

    def test_create_defaults_occurred_date_to_today(self):
        create = self.client.post(
            '/api/expenses/',
            {
                'category': self.cat.id,
                'description': 'Airtime',
                'amount': '100.00',
                'payment_method': 'mpesa',
                'status': 'pending',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        self.assertEqual(create.data['expense_date'], timezone.localdate().isoformat())

    def test_update_can_change_occurred_date_without_resetting_on_partial(self):
        occurred = timezone.localdate() - timedelta(days=6)
        expense = Expense.objects.create(
            category=self.cat,
            description='Diesel',
            amount=Decimal('500.00'),
            expense_date=occurred,
            payment_method='cash',
            status='pending',
            created_by=self.manager_user,
        )
        keep = self.client.patch(
            f'/api/expenses/{expense.id}/',
            {'description': 'Diesel for generator'},
            format='json',
        )
        self.assertEqual(keep.status_code, status.HTTP_200_OK, keep.data)
        expense.refresh_from_db()
        self.assertEqual(expense.expense_date, occurred)
        self.assertEqual(expense.description, 'Diesel for generator')

        moved = timezone.localdate() - timedelta(days=2)
        change = self.client.patch(
            f'/api/expenses/{expense.id}/',
            {'expense_date': moved.isoformat()},
            format='json',
        )
        self.assertEqual(change.status_code, status.HTTP_200_OK, change.data)
        self.assertEqual(change.data['expense_date'], moved.isoformat())


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
            created_by=self.admin,
        )
        response = self.client.get('/api/expenses/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_expenses', response.data)


class ExpenseCategoryAdminDeleteTests(SuperAdminAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from settings.models import ModuleSettings

        ModuleSettings.objects.update_or_create(
            module_name='expenses',
            defaults={'description': 'expenses', 'is_enabled': True},
        )
        cls.unused = ExpenseCategory.objects.create(name='Disposable', is_active=True)
        cls.used = ExpenseCategory.objects.create(name='In Use', is_active=True)
        Expense.objects.create(
            category=cls.used,
            description='Keeps category',
            amount=Decimal('5.00'),
            expense_date=timezone.now().date(),
            status='pending',
            created_by=cls.admin,
        )

    def test_admin_can_delete_unused_category(self):
        response = self.client.delete(f'/api/expenses/categories/{self.unused.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ExpenseCategory.objects.filter(id=self.unused.id).exists())

    def test_admin_cannot_delete_used_category(self):
        response = self.client.delete(f'/api/expenses/categories/{self.used.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(ExpenseCategory.objects.filter(id=self.used.id).exists())
        self.assertIn('used', (response.data.get('error') or '').lower())

    def test_category_list_includes_expense_count(self):
        response = self.client.get('/api/expenses/categories/?page_size=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', response.data)
        by_name = {r['name']: r for r in rows}
        self.assertEqual(by_name['In Use']['expense_count'], 1)
        self.assertEqual(by_name['Disposable']['expense_count'], 0)


class ExpenseCategoryManagerDeleteDeniedTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.unused = ExpenseCategory.objects.create(name='MgrDelete', is_active=True)

    def test_manager_cannot_delete_category(self):
        response = self.client.delete(f'/api/expenses/categories/{self.unused.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(ExpenseCategory.objects.filter(id=self.unused.id).exists())


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
