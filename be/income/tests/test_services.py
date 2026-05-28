"""Income service unit tests."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from income.models import Income, IncomeCategory
from income.services import IncomeService


class IncomeServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='inc_user', password='x')
        self.cat = IncomeCategory.objects.create(name='Services', is_active=True)
        self.service = IncomeService()

    def test_approve_income(self):
        income = Income.objects.create(
            category=self.cat,
            description='Consulting',
            amount=Decimal('500.00'),
            income_date=timezone.now().date(),
            status='pending',
            created_by=self.user,
        )
        approved = self.service.approve_income(income, self.user)
        self.assertEqual(approved.status, 'approved')

    def test_double_approve_raises(self):
        income = Income.objects.create(
            category=self.cat,
            description='Done',
            amount=Decimal('100.00'),
            income_date=timezone.now().date(),
            status='approved',
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            self.service.approve_income(income, self.user)

    def test_statistics(self):
        Income.objects.create(
            category=self.cat,
            description='Fee',
            amount=Decimal('300.00'),
            income_date=timezone.now().date(),
            status='approved',
            created_by=self.user,
        )
        stats = self.service.get_income_statistics()
        self.assertGreaterEqual(stats['total_income'], 300.0)
