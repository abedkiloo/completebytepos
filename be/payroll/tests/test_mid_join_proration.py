"""Unit, corrected, module, stress, and security tests for mid-join salary proration."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework import status

from accounts.role_definitions import ensure_permissions, sync_default_roles
from employees.models import Employee
from payroll.models import PayrollRun, PayrollSettings, Payslip
from payroll.proration import (
    apply_basic_proration,
    calendar_period_days,
    days_worked_in_period,
    mid_join_proration_factor,
    month_day_denominator,
)
from payroll.services import calculate_run, create_run
from payroll.starters import seed_starter_components
from settings.models import ModuleFeature, ModuleSettings
from utils.tests.api_test_base import SuperAdminAPITestCase


class MidJoinProrationUnitTests(SuperAdminAPITestCase):
    """Pure proration math (no DB payslips)."""

    def test_calendar_period_days_inclusive(self):
        self.assertEqual(
            calendar_period_days(date(2026, 3, 1), date(2026, 3, 31)), 31
        )
        self.assertEqual(
            calendar_period_days(date(2026, 2, 1), date(2026, 2, 28)), 28
        )

    def test_month_denominator_at_least_four_weeks(self):
        # Short synthetic span still floors at 28 days.
        self.assertEqual(
            month_day_denominator(date(2026, 3, 1), date(2026, 3, 10), min_month_days=28),
            28,
        )
        self.assertEqual(
            month_day_denominator(date(2026, 3, 1), date(2026, 3, 31), min_month_days=28),
            31,
        )

    def test_join_halfway_thirty_day_month_is_half(self):
        # Join on day 16 of a 30-day month → 15 days worked / 30 = 0.5
        factor = mid_join_proration_factor(
            hire_date=date(2026, 4, 16),
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            min_month_days=28,
        )
        self.assertEqual(factor, Decimal('0.500000'))

    def test_full_month_employee_gets_factor_one(self):
        factor = mid_join_proration_factor(
            hire_date=date(2025, 1, 1),
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            min_month_days=28,
        )
        self.assertEqual(factor, Decimal('1.000000'))

    def test_hired_after_period_zero_days(self):
        self.assertEqual(
            days_worked_in_period(
                hire_date=date(2026, 5, 1),
                period_start=date(2026, 4, 1),
                period_end=date(2026, 4, 30),
            ),
            0,
        )

    def test_apply_basic_proration_scales_money(self):
        amount, meta = apply_basic_proration(
            Decimal('40000.00'),
            hire_date=date(2026, 4, 16),
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            min_month_days=28,
            enabled=True,
        )
        self.assertEqual(amount, Decimal('20000.00'))
        self.assertTrue(meta['prorated'])
        self.assertEqual(meta['days_worked'], 15)

    def test_apply_disabled_returns_full(self):
        amount, meta = apply_basic_proration(
            Decimal('40000.00'),
            hire_date=date(2026, 4, 16),
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            enabled=False,
        )
        self.assertEqual(amount, Decimal('40000.00'))
        self.assertFalse(meta['prorated'])


class MidJoinProrationCorrectedTests(SuperAdminAPITestCase):
    """Corrected functionality: mid-join employee no longer gets full salary."""

    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles(created_by=self.admin)
        seed_starter_components()
        ModuleSettings.objects.update_or_create(
            module_name='payroll',
            defaults={'description': 'payroll', 'is_enabled': True},
        )
        settings = PayrollSettings.load()
        settings.prorate_mid_join = True
        settings.min_month_days = 28
        settings.save()

    def test_mid_month_hire_receives_half_basic_on_calculate(self):
        emp = Employee.objects.create(
            employee_id='JOIN-HALF',
            first_name='Half',
            last_name='Way',
            email='half.way@example.com',
            position='Clerk',
            department='admin',
            hire_date=date(2026, 4, 16),
            status='active',
            salary=Decimal('40000.00'),
            created_by=self.admin,
        )
        run = create_run(year=2026, month=4, user=self.admin)
        run = calculate_run(run, user=self.admin)
        slip = Payslip.objects.get(run=run, employee=emp)
        self.assertEqual(slip.basic_salary, Decimal('20000.00'))
        self.assertEqual(slip.net_pay, Decimal('20000.00'))
        self.assertTrue(slip.calculation_meta.get('proration', {}).get('prorated'))

    def test_full_month_hire_still_full_salary(self):
        emp = Employee.objects.create(
            employee_id='JOIN-FULL',
            first_name='Full',
            last_name='Month',
            email='full.month@example.com',
            position='Clerk',
            department='admin',
            hire_date=date(2026, 1, 1),
            status='active',
            salary=Decimal('40000.00'),
            created_by=self.admin,
        )
        run = create_run(year=2026, month=5, user=self.admin)
        run = calculate_run(run, user=self.admin)
        slip = Payslip.objects.get(run=run, employee=emp)
        self.assertEqual(slip.basic_salary, Decimal('40000.00'))


class MidJoinProrationIntegrationTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles(created_by=self.admin)
        seed_starter_components()
        ModuleSettings.objects.update_or_create(
            module_name='payroll',
            defaults={'description': 'payroll', 'is_enabled': True},
        )

    def test_settings_api_accepts_proration_fields(self):
        resp = self.client.patch(
            '/api/payroll/settings/',
            {'prorate_mid_join': True, 'min_month_days': 28},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(resp.data['prorate_mid_join'])
        self.assertEqual(resp.data['min_month_days'], 28)

    def test_settings_rejects_month_shorter_than_four_weeks(self):
        resp = self.client.patch(
            '/api/payroll/settings/',
            {'min_month_days': 20},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_calculate_prorates_mid_join(self):
        Employee.objects.create(
            employee_id='API-HALF',
            first_name='Api',
            last_name='Half',
            email='api.half@example.com',
            position='Clerk',
            department='admin',
            hire_date=date(2026, 6, 16),
            status='active',
            salary=Decimal('30000.00'),
            created_by=self.admin,
        )
        create = self.client.post(
            '/api/payroll/runs/',
            {'year': 2026, 'month': 6},
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        calc = self.client.post(f"/api/payroll/runs/{create.data['id']}/calculate/")
        self.assertEqual(calc.status_code, status.HTTP_200_OK, calc.data)
        slips = self.client.get(f"/api/payroll/runs/{create.data['id']}/payslips/")
        self.assertEqual(slips.status_code, status.HTTP_200_OK)
        rows = slips.data if isinstance(slips.data, list) else slips.data.get('results', [])
        row = next(s for s in rows if s.get('employee_id_snapshot') == 'API-HALF')
        # List serializer may omit basic; assert via net / detail when needed.
        basic = row.get('basic_salary')
        if basic is None:
            detail = self.client.get(f"/api/payroll/payslips/{row['id']}/")
            self.assertEqual(detail.status_code, status.HTTP_200_OK, detail.data)
            basic = detail.data['basic_salary']
        self.assertEqual(Decimal(str(basic)), Decimal('15000.00'))


class MidJoinProrationModuleTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles(created_by=self.admin)
        seed_starter_components()
        self.mod, _ = ModuleSettings.objects.update_or_create(
            module_name='payroll',
            defaults={'description': 'payroll', 'is_enabled': True},
        )
        self.feat, _ = ModuleFeature.objects.update_or_create(
            module=self.mod,
            feature_key='mid_join_proration',
            defaults={
                'feature_name': 'Mid-join salary proration',
                'is_enabled': True,
            },
        )
        settings = PayrollSettings.load()
        settings.prorate_mid_join = True
        settings.save()

    def test_feature_off_pays_full_salary(self):
        self.feat.is_enabled = False
        self.feat.save(update_fields=['is_enabled'])
        emp = Employee.objects.create(
            employee_id='FEAT-OFF',
            first_name='Feat',
            last_name='Off',
            email='feat.off@example.com',
            position='Clerk',
            department='admin',
            hire_date=date(2026, 7, 16),
            status='active',
            salary=Decimal('40000.00'),
            created_by=self.admin,
        )
        run = create_run(year=2026, month=7, user=self.admin)
        run = calculate_run(run, user=self.admin)
        slip = Payslip.objects.get(run=run, employee=emp)
        self.assertEqual(slip.basic_salary, Decimal('40000.00'))

    def test_setting_off_pays_full_salary(self):
        settings = PayrollSettings.load()
        settings.prorate_mid_join = False
        settings.save()
        emp = Employee.objects.create(
            employee_id='SET-OFF',
            first_name='Set',
            last_name='Off',
            email='set.off@example.com',
            position='Clerk',
            department='admin',
            hire_date=date(2026, 8, 16),
            status='active',
            salary=Decimal('40000.00'),
            created_by=self.admin,
        )
        run = create_run(year=2026, month=8, user=self.admin)
        run = calculate_run(run, user=self.admin)
        slip = Payslip.objects.get(run=run, employee=emp)
        self.assertEqual(slip.basic_salary, Decimal('40000.00'))


class MidJoinProrationStressTests(SuperAdminAPITestCase):
    def test_many_hire_offsets_stay_within_bounds(self):
        start, end = date(2026, 3, 1), date(2026, 3, 31)
        for day in range(1, 32):
            factor = mid_join_proration_factor(
                hire_date=date(2026, 3, day),
                period_start=start,
                period_end=end,
                min_month_days=28,
            )
            self.assertGreaterEqual(factor, Decimal('0'))
            self.assertLessEqual(factor, Decimal('1'))
            amount, _ = apply_basic_proration(
                Decimal('100000.00'),
                hire_date=date(2026, 3, day),
                period_start=start,
                period_end=end,
                enabled=True,
            )
            self.assertGreaterEqual(amount, Decimal('0'))
            self.assertLessEqual(amount, Decimal('100000.00'))


class MidJoinProrationSecurityTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles(created_by=self.admin)
        seed_starter_components()
        ModuleSettings.objects.update_or_create(
            module_name='payroll',
            defaults={'description': 'payroll', 'is_enabled': True},
        )

    def test_unauthenticated_settings_denied(self):
        self.client.credentials()
        resp = self.client.get('/api/payroll/settings/')
        self.assertIn(resp.status_code, (401, 403))

    def test_sales_role_cannot_patch_proration_settings(self):
        sales = User.objects.create_user(username='pay_sales', password='x')
        from accounts.models import Role, UserProfile
        from accounts.role_definitions import ROLE_SALES

        role = Role.objects.filter(name=ROLE_SALES).first()
        UserProfile.objects.create(
            user=sales, role='sales', custom_role=role, is_active=True
        )
        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken.for_user(sales)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        resp = self.client.patch(
            '/api/payroll/settings/',
            {'prorate_mid_join': False, 'min_month_days': 28},
            format='json',
        )
        self.assertIn(resp.status_code, (403, 401))

    def test_hired_after_period_excluded_from_run(self):
        ps = PayrollSettings.load()
        ps.prorate_mid_join = True
        ps.save()
        with patch(
            'payroll.services._mid_join_proration_enabled', return_value=True
        ):
            emp = Employee.objects.create(
                employee_id='FUTURE',
                first_name='Future',
                last_name='Hire',
                email='future.hire@example.com',
                position='Clerk',
                department='admin',
                hire_date=date(2026, 10, 1),
                status='active',
                salary=Decimal('40000.00'),
                created_by=self.admin,
            )
            run = create_run(year=2026, month=9, user=self.admin)
            run = calculate_run(run, user=self.admin)
            self.assertFalse(
                Payslip.objects.filter(run=run, employee=emp).exists()
            )
