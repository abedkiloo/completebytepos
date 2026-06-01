"""Extended income queryset, statistics, and API coverage."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from income.models import Income, IncomeCategory
from income.services import IncomeCategoryService, IncomeService
from utils.tests.api_test_base import ManagerAPITestCase


class IncomeQuerysetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='inc_qs', password='x')
        self.service = IncomeService()
        self.cat = IncomeCategory.objects.create(name='Services', is_active=True)
        today = timezone.now().date()
        Income.objects.create(
            category=self.cat,
            description='Pending fee',
            amount=Decimal('100.00'),
            income_date=today,
            status='pending',
            payment_method='cash',
            created_by=self.user,
        )
        Income.objects.create(
            category=self.cat,
            description='Approved fee',
            amount=Decimal('400.00'),
            income_date=today,
            status='approved',
            payment_method='bank',
            created_by=self.user,
        )
        Income.objects.create(
            category=self.cat,
            description='Last month',
            amount=Decimal('150.00'),
            income_date=today - timedelta(days=35),
            status='approved',
            payment_method='mpesa',
            created_by=self.user,
        )

    def test_build_queryset_payment_method_filter(self):
        qs = self.service.build_queryset({'payment_method': 'bank'})
        self.assertEqual(qs.count(), 1)

    def test_statistics_pending_excluded_from_total(self):
        stats = self.service.get_income_statistics()
        self.assertEqual(stats['total_income'], 550.0)
        statuses = {row['status'] for row in stats['by_status']}
        self.assertIn('pending', statuses)
        self.assertIn('approved', statuses)

    def test_category_service_inactive_excluded(self):
        IncomeCategory.objects.create(name='Legacy', is_active=False)
        qs = IncomeCategoryService().build_queryset({'is_active': True})
        self.assertFalse(qs.filter(name='Legacy').exists())


class IncomeAPIExtendedTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cat = IncomeCategory.objects.create(name='Fees', is_active=True)

    def test_double_approve_returns_400(self):
        create = self.client.post(
            '/api/income/',
            {
                'category': self.cat.id,
                'description': 'Consulting',
                'amount': '120.00',
                'income_date': timezone.now().date().isoformat(),
                'payment_method': 'cash',
                'status': 'pending',
            },
            format='json',
        )
        income_id = create.data['id']
        self.client.post(f'/api/income/{income_id}/approve/')
        again = self.client.post(f'/api/income/{income_id}/approve/')
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)

    def test_statistics_reflects_approved_only(self):
        Income.objects.create(
            category=self.cat,
            description='Approved',
            amount=Decimal('300.00'),
            income_date=timezone.now().date(),
            status='approved',
            payment_method='bank',
            created_by=self.manager_user,
        )
        response = self.client.get('/api/income/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['total_income'], 300.0)

    def test_category_crud(self):
        response = self.client.post(
            '/api/income/categories/',
            {'name': 'Donations', 'is_active': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
