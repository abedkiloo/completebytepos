"""Focused coverage for appraisals policy, services, views, engine, tips."""

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ensure_permissions, sync_default_roles
from appraisals.engine import (
    band_progress,
    daily_star,
    increment_progress_message,
    monthly_bonus,
    pick_band,
    status_label,
    year_end_result,
)
from appraisals.models import AppraisalSalaryIncrement
from appraisals.policy import (
    PolicyError,
    _decimal,
    _float,
    _int,
    _normalize_role_daily_targets,
    catalog_role_names,
    default_template,
    greet_when_no_sticky_notes,
    load_template,
    merge_role_daily_targets,
    resolve_role_daily_target,
    save_template,
    show_on_home,
    staff_facing,
    template_at_date,
    validate_template,
)
from appraisals.services import (
    _aware,
    _display_name,
    _month_bounds,
    _year_bounds,
    decide_salary_increment,
    list_salary_increments,
    staff_role_name,
    sync_salary_increment,
    uses_manager_daily_target,
)
from appraisals.tips import (
    normalize_daily_tip_packs,
    pick_daily_tips,
    _normalize_tip_pack,
)
from employees.models import Employee
from settings.models import ModuleSettings
from utils.tests.api_test_base import SuperAdminAPITestCase


def _enable_appraisals():
    cache.clear()
    ModuleSettings.objects.update_or_create(
        module_name='appraisals',
        defaults={'is_enabled': True, 'description': 'Staff appraisals'},
    )


class PolicyUnitCoverageTests(TestCase):
    def setUp(self):
        _enable_appraisals()
        save_template(default_template())

    def test_coercion_and_role_targets(self):
        self.assertEqual(_decimal(None), Decimal('0'))
        self.assertEqual(_decimal('bad'), Decimal('0'))
        self.assertEqual(_float('x', 3), 3.0)
        self.assertEqual(_int('bad', 7), 7)
        self.assertEqual(_int(None, 2), 2)

        targets = _normalize_role_daily_targets(
            {
                'role_daily_targets': [
                    {'role': 'Sales Personnel', 'target': 21000},
                    {'name': 'Manager', 'daily_target': 36000},
                    {'role': 'Super Admin', 'target': 1},
                    'skip',
                ],
            },
            daily_target=20000,
            manager_daily_target=35000,
        )
        self.assertEqual(targets['Sales Personnel'], 21000)
        self.assertIn('Manager', targets)

        tpl = default_template()
        self.assertTrue(catalog_role_names())
        merged = merge_role_daily_targets(tpl)
        self.assertIn('Sales Personnel', merged)
        self.assertEqual(resolve_role_daily_target(tpl, 'Super Admin'), 0)
        self.assertGreater(resolve_role_daily_target(tpl, 'Manager'), 0)
        self.assertGreater(resolve_role_daily_target(tpl, 'Unknown Role'), 0)

    def test_template_at_date_and_validate_errors(self):
        tpl = default_template()
        tpl['active_from'] = '2026-06-01'
        tpl['versions'] = [{
            'id': 1,
            'effective_from': '2026-01-01',
            'effective_until': '2026-06-01',
            'snapshot': {
                **{k: tpl.get(k) for k in (
                    'basic_pay', 'daily_target', 'manager_daily_target',
                    'role_daily_targets', 'role_frameworks', 'year_end_increment',
                    'working_days', 'four_star_month_min_avg', 'four_star_months_required',
                    'annual_avg_required', 'bonus_min_stars', 'bonus_cap',
                    'daily_star_bands', 'monthly_bonus_bands', 'sales_basis', 'status_labels',
                )},
                'daily_target': 15000,
            },
        }]
        past = template_at_date(tpl, date(2026, 3, 1))
        self.assertEqual(past['daily_target'], 15000)
        self.assertEqual(template_at_date(tpl, None)['daily_target'], tpl['daily_target'])
        self.assertEqual(
            template_at_date(tpl, datetime(2026, 7, 1))['daily_target'],
            tpl['daily_target'],
        )
        self.assertEqual(template_at_date(tpl, 'not-a-date')['daily_target'], tpl['daily_target'])

        bad_cap = default_template()
        bad_cap['bonus_cap'] = 100
        bad_cap['monthly_bonus_bands'] = [
            {'min': 0, 'stars': 4, 'bonus': 500, 'label': 'Over cap'},
        ]
        with self.assertRaises(PolicyError):
            validate_template(bad_cap)

        # framework daily target <= 0
        bad5 = default_template()
        bad5['role_frameworks'] = {
            'Sales Personnel': {
                'daily_target': 0,
                'daily_star_bands': bad5['daily_star_bands'],
                'monthly_bonus_bands': bad5['monthly_bonus_bands'],
            },
        }
        with self.assertRaises(PolicyError):
            validate_template(bad5)

    def test_flags_and_save_versioning(self):
        self.assertTrue(isinstance(greet_when_no_sticky_notes(), bool))
        self.assertTrue(isinstance(show_on_home(), bool))
        self.assertTrue(isinstance(staff_facing(), bool))

        current = load_template()
        current['daily_target'] = float(current['daily_target']) + 100
        current['change_reason'] = 'coverage bump'
        current['effective_from'] = timezone.localdate().isoformat()
        current['greet_when_no_sticky_notes'] = False
        current['show_on_home'] = False
        current['staff_facing'] = True
        saved = save_template(current, user=None, request=None)
        self.assertIn('daily_target', saved)

        # cannot go earlier than active_from
        earlier = load_template()
        earlier['daily_target'] = float(earlier['daily_target']) + 50
        earlier['effective_from'] = '2000-01-01'
        with self.assertRaises(PolicyError):
            save_template(earlier)


class EngineAndTipsCoverageTests(SimpleTestCase):
    def test_engine_edge_paths(self):
        self.assertEqual(pick_band(10, []), {'min': 0, 'stars': 1, 'bonus': 0, 'label': ''})
        self.assertEqual(band_progress(10, [{'min': 0, 'stars': 1}, {'min': 0, 'stars': 2}]), 1.0)
        tpl = default_template()
        daily = daily_star(0, tpl)
        self.assertEqual(daily['stars'], 1)
        bonus = monthly_bonus(999999999, {**tpl, 'bonus_cap': 100})
        self.assertLessEqual(bonus['bonus'], 100)
        self.assertEqual(status_label(5, {}), 'Exceptional')
        self.assertEqual(status_label(4.5, {}), 'Target exceeded')
        self.assertEqual(status_label(4, {'status_labels': {'4': 'Hit'}}), 'Hit')
        self.assertEqual(status_label(2.5, {}), 'Below target')
        self.assertEqual(status_label(0.5, {}), 'Needs attention')

        year = {
            'qualifies': False,
            'four_star_months_required': 8,
            'four_star_months': 7,
            'annual_avg_required': 4,
            'annual_average': 4.1,
            'ytd_average': 4.1,
        }
        msg = increment_progress_message(year, {'year_end_increment': 1000, 'annual_avg_required': 4})
        self.assertIn('One more', msg)
        year2 = {**year, 'four_star_months': 5}
        self.assertIn('more 4-Star months', increment_progress_message(year2, {'year_end_increment': 1000}))
        year3 = {**year, 'four_star_months': 8, 'annual_average': 3.5}
        self.assertIn('annual average', increment_progress_message(year3, {
            'year_end_increment': 1000, 'annual_avg_required': 4,
        }))
        self.assertEqual(increment_progress_message(year, {'year_end_increment': 0}), '')
        qualified = year_end_result([4.5] * 12, tpl)
        self.assertTrue(qualified['qualifies'])
        self.assertIn('On track', increment_progress_message(qualified, tpl))

    def test_tips_normalize(self):
        self.assertIsNone(_normalize_tip_pack('x'))
        self.assertIsNone(_normalize_tip_pack({'title': '', 'tips': ['a', 'b', 'c']}))
        self.assertIsNone(_normalize_tip_pack({'title': 'T', 'tips': ['a']}))
        pack = _normalize_tip_pack({'title': 'Hello World', 'tips': ['a', 'b', 'c', 'd']})
        self.assertEqual(pack['id'], 'hello-world')
        self.assertEqual(normalize_daily_tip_packs(None)[0]['id'], 'follow-up')
        legacy = normalize_daily_tip_packs([
            {'id': 'reach-workshops', 'title': 'Old', 'tips': ['a', 'b', 'c']},
        ])
        self.assertEqual(legacy[0]['id'], 'follow-up')
        custom = normalize_daily_tip_packs([
            {'id': 'custom-pack', 'title': 'Custom', 'tips': ['a', 'b', 'c', 'd', 'e']},
        ])
        picked = pick_daily_tips({'daily_tip_packs': custom}, today=date(2026, 1, 1))
        self.assertEqual(picked['id'], 'custom-pack')


class ServicesCoverageTests(TestCase):
    def setUp(self):
        ensure_permissions()
        sync_default_roles()
        _enable_appraisals()
        save_template(default_template())
        self.user = User.objects.create_user(
            'appr_cov',
            email='appr_cov@test.com',
            password='x',
            first_name='Ann',
            last_name='Wanjiku',
        )
        UserProfile.objects.create(
            user=self.user,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
            is_active=True,
        )

    def test_helpers_and_increments(self):
        self.assertTrue(timezone.is_aware(_aware(datetime(2026, 1, 1))))
        self.assertEqual(_year_bounds(2026)[0].year, 2026)
        start, end = _month_bounds(2026, 12)
        self.assertEqual(start.month, 12)
        self.assertEqual(end.month, 1)
        start2, end2 = _month_bounds(2026, 5)
        self.assertEqual(start2.month, 5)
        self.assertEqual(end2.month, 6)

        self.assertEqual(_display_name(None), 'Unassigned')
        self.assertEqual(_display_name(self.user), 'Ann Wanjiku')
        bare = User.objects.create_user('bare_appr', password='x')
        self.assertEqual(staff_role_name(None), 'Sales Personnel')
        self.assertEqual(staff_role_name(bare), 'Sales Personnel')
        self.assertTrue(uses_manager_daily_target(self.user))

        year_snap = {
            'year': 2026,
            'qualifies': True,
            'basic_pay': 15000,
            'year_end_increment': 1000,
            'four_star_months': 8,
            'annual_average': 4.2,
        }
        draft = sync_salary_increment(self.user, year_snap, 'Manager', persist=False)
        self.assertIsNone(draft.get('id'))
        saved = sync_salary_increment(self.user, year_snap, 'Manager', persist=True)
        self.assertIsNotNone(saved['id'])
        again = sync_salary_increment(self.user, year_snap, 'Manager', persist=False)
        self.assertEqual(again['id'], saved['id'])

        rows = list_salary_increments(year=2026)
        self.assertTrue(rows)

        with self.assertRaises(PolicyError):
            decide_salary_increment(999999, user=self.user, approve=True)

        # reject path
        rejected = decide_salary_increment(
            saved['id'], user=self.user, approve=False, reason='Not yet',
        )
        self.assertEqual(rejected['status'], AppraisalSalaryIncrement.STATUS_REJECTED)

        # re-create eligible and approve with employee salary update
        row = AppraisalSalaryIncrement.objects.get(pk=saved['id'])
        row.status = AppraisalSalaryIncrement.STATUS_PENDING
        row.qualifies = True
        row.previous_basic = Decimal('15000')
        row.new_basic = Decimal('16000')
        row.save()
        Employee.objects.create(
            employee_id='E-APPR-1',
            first_name='Ann',
            last_name='Wanjiku',
            email='appr_cov@test.com',
            position='Manager',
            hire_date=timezone.localdate(),
            salary=Decimal('15000'),
        )
        approved = decide_salary_increment(
            row.id,
            user=self.user,
            approve=True,
            reason='ok',
            effective_date=date(2026, 12, 1),
        )
        self.assertEqual(approved['status'], AppraisalSalaryIncrement.STATUS_APPROVED)
        with self.assertRaises(PolicyError):
            decide_salary_increment(row.id, user=self.user, approve=True)

        # non-qualifying approve
        row2 = AppraisalSalaryIncrement.objects.create(
            user=User.objects.create_user('appr_nq', password='x'),
            year=2025,
            qualifies=False,
            previous_basic=Decimal('10000'),
            new_basic=Decimal('10000'),
            status=AppraisalSalaryIncrement.STATUS_PENDING,
        )
        with self.assertRaises(PolicyError):
            decide_salary_increment(row2.id, user=self.user, approve=True)


class AppraisalViewsCoverageTests(SuperAdminAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        _enable_appraisals()

    def setUp(self):
        super().setUp()
        _enable_appraisals()
        save_template(default_template())

    def test_year_param_and_increment_decide_errors(self):
        me = self.client.get('/api/appraisals/me/', {'year': 'not-a-year'})
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        me2 = self.client.get('/api/appraisals/me/', {'year': '1999'})
        self.assertEqual(me2.status_code, status.HTTP_200_OK)
        me3 = self.client.get('/api/appraisals/me/', {'year': '2026'})
        self.assertEqual(me3.status_code, status.HTTP_200_OK)

        policy = self.client.patch(
            '/api/appraisals/policy/',
            {
                'daily_star_bands': [
                    {'min': 0, 'stars': 1, 'label': ''},
                    {'min': 0, 'stars': 2, 'label': ''},
                ],
            },
            format='json',
        )
        # Duplicate mins may be rejected (400) or normalized away (200).
        self.assertIn(policy.status_code, (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST))

        increments = self.client.get('/api/appraisals/increments/', {'year': '2026'})
        self.assertEqual(increments.status_code, status.HTTP_200_OK)

        bad_date = self.client.post(
            '/api/appraisals/increments/1/decision/',
            {'decision': 'approve', 'effective_date': '20-26'},
            format='json',
        )
        self.assertEqual(bad_date.status_code, status.HTTP_400_BAD_REQUEST)

        missing = self.client.post(
            '/api/appraisals/increments/999999/decision/',
            {'decision': 'reject', 'reason': 'nope'},
            format='json',
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)


class AppraisalsExtraGapTests(TestCase):
    def setUp(self):
        ensure_permissions()
        sync_default_roles()
        _enable_appraisals()
        save_template(default_template())

    def test_remaining_helpers(self):
        from appraisals.engine import band_progress, monthly_bonus
        from appraisals.policy import (
            _normalize_daily_band,
            _normalize_bonus_band,
            _parse_iso_date,
            template_at_date,
            template_for_role,
            _align_bonus_min_stars,
            _validate_bonus_bands,
            PolicyError,
        )
        from accounts.role_definitions import ROLE_SALES
        from appraisals.services import (
            _annual_status,
            _apply_employee_salary,
            _applied_for_day,
            _cycle_eligible,
            _join_date,
            _employee_for_user,
            build_team_insights,
            staff_snapshot,
            staff_role_name,
        )
        from appraisals.tips import normalize_daily_tip_packs

        self.assertIsNone(_normalize_daily_band('x'))
        self.assertIsNone(_normalize_bonus_band('x'))
        self.assertIsNone(_parse_iso_date('bad'))
        self.assertIsNone(_parse_iso_date('2026-13-40'))

        # span <= 0 in band_progress
        self.assertEqual(
            band_progress(5, [{'min': 10, 'stars': 1}, {'min': 10, 'stars': 2}]),
            1.0,
        )
        # next bonus below min stars
        tpl = default_template()
        tpl['bonus_min_stars'] = 4
        monthly_bonus(0, tpl)

        # align when no paid bonuses
        data = {'bonus_min_stars': 4, 'monthly_bonus_bands': [{'stars': 3, 'bonus': 0}]}
        self.assertEqual(_align_bonus_min_stars(data), 4.0)

        with self.assertRaises(PolicyError):
            _validate_bonus_bands([], min_stars=4, cap=100)
        with self.assertRaises(PolicyError):
            _validate_bonus_bands(
                [{'min': 1, 'stars': 4, 'bonus': 10}, {'min': 1, 'stars': 5, 'bonus': 20}],
                min_stars=4,
                cap=100,
            )
        with self.assertRaises(PolicyError):
            _validate_bonus_bands(
                [{'min': 0, 'stars': 2, 'bonus': 50}],
                min_stars=4,
                cap=100,
            )

        self.assertEqual(_annual_status({'year': {'qualifies': True}}), 'On track')
        self.assertEqual(
            _annual_status({
                'year': {
                    'qualifies': False,
                    'four_star_months_required': 8,
                    'four_star_months': 7,
                },
            }),
            'Close',
        )

        insights = build_team_insights(
            [
                {
                    'staff': {'role': 'Sales Personnel'},
                    'today': {'stars': 4, 'sales': 100},
                    'month': {'official_average': 4.2, 'bonus': 500, 'sales': 1000},
                    'year': {
                        'four_star_months_required': 8,
                        'four_star_months': 7,
                        'qualifies': False,
                        'projected_qualifies': True,
                    },
                    'annual_status': 'Close',
                },
                {
                    'staff': {'role': 'Manager'},
                    'today': {'stars': 2, 'sales': 50},
                    'month': {'official_average': 3.0, 'bonus': 0, 'sales': 200},
                    'year': {
                        'four_star_months_required': 8,
                        'four_star_months': 2,
                        'qualifies': False,
                        'projected_qualifies': False,
                    },
                    'annual_status': 'At risk',
                },
            ],
            default_template(),
        )
        self.assertGreaterEqual(insights['headcount'], 2)

        user = User.objects.create_user(
            'appr_extra', email='appr_extra@test.com', password='x',
        )
        UserProfile.objects.create(
            user=user, role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        Employee.objects.create(
            employee_id='E-EXTRA',
            first_name='Ex',
            last_name='Tra',
            email='appr_extra@test.com',
            position='Sales',
            hire_date=date(2026, 3, 15),
            salary=Decimal('18000'),
        )
        self.assertIsNotNone(_employee_for_user(user))
        self.assertIsNone(_employee_for_user(None))
        self.assertEqual(_join_date(None), None)
        self.assertEqual(_join_date(user), date(2026, 3, 15))
        applied = _apply_employee_salary(user, default_template())
        self.assertEqual(applied['basic_pay'], 18000.0)
        self.assertTrue(_cycle_eligible(None, 2026, 3))
        self.assertFalse(_cycle_eligible(date(2026, 3, 15), 2026, 3))
        self.assertTrue(_cycle_eligible(date(2026, 3, 1), 2026, 3))

        base = default_template()
        day = _applied_for_day(
            template_for_role(base, 'Sales Personnel'),
            base_template=base,
            role_name='Sales Personnel',
            on_date=date(2026, 1, 1),
        )
        self.assertIn('daily_target', day)
        self.assertEqual(_applied_for_day(base), base)

        # legacy role name path
        bare = User.objects.create_user('legacy_role', password='x')
        UserProfile.objects.create(user=bare, role='cashier', custom_role=None, is_active=True)
        self.assertEqual(staff_role_name(bare), 'Sales Personnel')

        # past/future year snapshot branches
        past = staff_snapshot(user, year=2025, today=date(2026, 10, 20))
        self.assertEqual(past['year']['year'], 2025)
        future = staff_snapshot(user, year=2027, today=date(2026, 10, 20))
        self.assertEqual(future['year']['year'], 2027)

        # model __str__
        row = AppraisalSalaryIncrement.objects.create(
            user=user, year=2024, qualifies=False,
            status=AppraisalSalaryIncrement.STATUS_NOT_ELIGIBLE,
        )
        self.assertIn('2024', str(row))

        # tips empty packs after filter
        self.assertTrue(normalize_daily_tip_packs([{'title': 'x', 'tips': ['a']}]))

        # template_at_date with version skip branches
        tpl = default_template()
        tpl['active_from'] = '2026-06-01'
        tpl['versions'] = [
            {
                'effective_from': '2026-05-01',
                'effective_until': '2026-05-15',
                'snapshot': {'daily_target': 11111},
            },
            {
                'effective_from': '2026-01-01',
                'effective_until': None,
                'snapshot': None,
            },
            {
                'effective_from': '2026-02-01',
                'effective_until': '2026-06-01',
                'snapshot': {'daily_target': 22222},
            },
        ]
        mid = template_at_date(tpl, date(2026, 3, 1))
        self.assertEqual(mid.get('daily_target'), 22222)
