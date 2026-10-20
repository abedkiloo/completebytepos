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

    def test_reject_resubmit_and_void(self):
        create = self.client.post(
            '/api/income/',
            {
                'category': self.cat.id,
                'description': 'To reject',
                'amount': '40.00',
                'income_date': timezone.now().date().isoformat(),
                'payment_method': 'cash',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        income_id = create.data['id']

        reject = self.client.post(
            f'/api/income/{income_id}/reject/',
            {'rejection_reason': 'Incomplete'},
            format='json',
        )
        self.assertEqual(reject.status_code, status.HTTP_200_OK, reject.data)
        self.assertIn(reject.data['status'], ('rejected', 'cancelled'))

        resubmit = self.client.post(f'/api/income/{income_id}/resubmit/')
        self.assertEqual(resubmit.status_code, status.HTTP_200_OK, resubmit.data)
        self.assertEqual(resubmit.data['status'], 'pending')

        void = self.client.post(
            f'/api/income/{income_id}/void/',
            {'reason': 'Entered twice'},
            format='json',
        )
        self.assertEqual(void.status_code, status.HTTP_200_OK, void.data)
        self.assertEqual(void.data['status'], 'voided')

        missing_reason = self.client.post(
            f'/api/income/{income_id}/reject/',
            {},
            format='json',
        )
        self.assertEqual(missing_reason.status_code, status.HTTP_400_BAD_REQUEST)

        # Already voided → service ValidationError path on void
        void_again = self.client.post(
            f'/api/income/{income_id}/void/',
            {'reason': 'again'},
            format='json',
        )
        self.assertEqual(void_again.status_code, status.HTTP_400_BAD_REQUEST)

        pending = self.client.post(
            '/api/income/',
            {
                'category': self.cat.id,
                'description': 'Needs reason',
                'amount': '12.00',
                'income_date': timezone.now().date().isoformat(),
                'payment_method': 'cash',
            },
            format='json',
        )
        self.assertEqual(pending.status_code, status.HTTP_201_CREATED, pending.data)
        void_no_reason = self.client.post(
            f'/api/income/{pending.data["id"]}/void/',
            {'reason': '   '},
            format='json',
        )
        self.assertEqual(void_no_reason.status_code, status.HTTP_400_BAD_REQUEST)


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
