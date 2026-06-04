"""Income API tests."""

from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from income.models import IncomeCategory
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase, SuperAdminAPITestCase


class IncomeViewsTestCase(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cat = IncomeCategory.objects.create(name='Fees', is_active=True)

    def test_manager_can_create_but_not_approve_income(self):
        create = self.client.post(
            '/api/income/',
            {
                'category': self.cat.id,
                'description': 'Service fee',
                'amount': '750.00',
                'income_date': timezone.now().date().isoformat(),
                'payment_method': 'bank',
                'status': 'pending',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        approve = self.client.post(f'/api/income/{create.data["id"]}/approve/')
        self.assertEqual(approve.status_code, status.HTTP_403_FORBIDDEN)


class IncomeApproveSuperAdminTests(SuperAdminAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cat = IncomeCategory.objects.create(name='Fees SA', is_active=True)

    def test_super_admin_can_approve_income(self):
        create = self.client.post(
            '/api/income/',
            {
                'category': self.cat.id,
                'description': 'Grant',
                'amount': '100.00',
                'income_date': timezone.now().date().isoformat(),
                'payment_method': 'cash',
                'status': 'pending',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        approve = self.client.post(f'/api/income/{create.data["id"]}/approve/')
        self.assertEqual(approve.status_code, status.HTTP_200_OK)

    def test_statistics(self):
        response = self.client.get('/api/income/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class IncomePermissionsTestCase(SalesAPITestCase):
    def test_sales_cannot_approve_income(self):
        cat = IncomeCategory.objects.create(name='X')
        from income.models import Income

        income = Income.objects.create(
            category=cat,
            description='X',
            amount=Decimal('10'),
            income_date=timezone.now().date(),
            status='pending',
            created_by=self.sales_user,
        )
        response = self.client.post(f'/api/income/{income.id}/approve/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
