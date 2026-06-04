"""Income service unit tests."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from income.models import Income, IncomeCategory
from income.services import IncomeCategoryService, IncomeService
from settings.models import StoreSettings


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

    def test_maker_checker_blocks_self_approve(self):
        store = StoreSettings.load()
        store.maker_checker_enabled = True
        store.save(update_fields=['maker_checker_enabled'])
        income = Income.objects.create(
            category=self.cat,
            description='Fee',
            amount=Decimal('90.00'),
            income_date=timezone.now().date(),
            status='pending',
            created_by=self.user,
        )
        checker = User.objects.create_user(username='checker_inc', password='x')
        with self.assertRaises(DRFValidationError):
            self.service.approve_income(income, self.user)
        approved = self.service.approve_income(income, checker)
        self.assertEqual(approved.status, 'approved')
        store.maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled'])

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

    def test_build_queryset_none_filters_defaults(self):
        Income.objects.create(
            category=self.cat,
            description='Any',
            amount=Decimal('1.00'),
            income_date=timezone.now().date(),
            status='approved',
            created_by=self.user,
        )
        self.assertGreaterEqual(self.service.build_queryset(None).count(), 1)

    def test_build_queryset_filters(self):
        from income.services import IncomeCategoryService

        Income.objects.create(
            category=self.cat,
            description='Pending fee',
            amount=Decimal('120.00'),
            income_date=timezone.now().date(),
            status='pending',
            payment_method='mpesa',
            created_by=self.user,
        )
        qs = self.service.build_queryset({
            'category': self.cat.id,
            'status': 'pending',
            'payment_method': 'mpesa',
            'show_all': 'true',
        })
        self.assertEqual(qs.count(), 1)
        IncomeCategory.objects.create(name='Old', is_active=False)
        active_cats = IncomeCategoryService().build_queryset({'is_active': 'false'})
        self.assertEqual(active_cats.count(), 1)

    def test_build_queryset_branch_and_date_filters(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, branch_b = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='INC'
        )
        today = timezone.now().date()
        Income.objects.create(
            category=self.cat,
            description='Branch income',
            amount=Decimal('80.00'),
            income_date=today,
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

    def test_category_service_no_filters_returns_all(self):
        self.assertGreaterEqual(IncomeCategoryService().build_queryset().count(), 1)

    def test_category_service_is_active_true_string(self):
        IncomeCategory.objects.create(name='Inactive', is_active=False)
        qs = IncomeCategoryService().build_queryset({'is_active': 'true'})
        self.assertTrue(qs.filter(name='Services').exists())
        self.assertFalse(qs.filter(name='Inactive').exists())

    def test_build_queryset_resolves_branch_from_request(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, _ = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='INR'
        )
        Income.objects.create(
            category=self.cat,
            description='Session income',
            amount=Decimal('25.00'),
            income_date=timezone.now().date(),
            status='approved',
            branch=branch_a,
            created_by=self.user,
        )
        request = RequestFactory().get('/api/income/')
        with patch('income.services.get_current_branch', return_value=branch_a):
            qs = self.service.build_queryset({'show_all': 'false'}, request=request)
        self.assertEqual(qs.count(), 1)

    def test_build_queryset_invalid_branch_id_returns_empty(self):
        qs = self.service.build_queryset({'branch_id': 'bad'})
        self.assertEqual(qs.count(), 0)

    def test_build_queryset_invalid_category_id_returns_empty(self):
        qs = self.service.build_queryset({'category': 'bad'})
        self.assertEqual(qs.count(), 0)

    def test_build_queryset_payment_method_filter(self):
        Income.objects.create(
            category=self.cat,
            description='Mpesa',
            amount=Decimal('50.00'),
            income_date=timezone.now().date(),
            status='approved',
            payment_method='mpesa',
            created_by=self.user,
        )
        qs = self.service.build_queryset({'payment_method': 'mpesa'})
        self.assertEqual(qs.count(), 1)

    def test_approve_journal_failure_is_non_fatal(self):
        income = Income.objects.create(
            category=self.cat,
            description='Journal fail',
            amount=Decimal('10.00'),
            income_date=timezone.now().date(),
            status='pending',
            created_by=self.user,
        )
        with patch(
            'accounting.services.create_income_journal_entry',
            side_effect=RuntimeError('ledger offline'),
        ):
            approved = self.service.approve_income(income, self.user)
        self.assertEqual(approved.status, 'approved')

    def test_statistics_with_branch_and_date_range(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, _ = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='INS'
        )
        today = timezone.now().date()
        Income.objects.create(
            category=self.cat,
            description='Scoped income',
            amount=Decimal('90.00'),
            income_date=today,
            status='approved',
            branch=branch_a,
            created_by=self.user,
        )
        stats = self.service.get_income_statistics(
            branch=branch_a,
            date_from=today,
            date_to=today,
        )
        self.assertGreaterEqual(stats['total_income'], 90.0)

    def test_build_queryset_invalid_category_returns_empty(self):
        qs = self.service.build_queryset({'category': 'x', 'show_all': 'true'})
        self.assertEqual(qs.count(), 0)
