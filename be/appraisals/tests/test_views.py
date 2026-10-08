from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_FIELD_AGENT
from appraisals.policy import default_template, save_template
from sales.models import Sale
from settings.models import ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase, SuperAdminAPITestCase


def _enable_appraisals():
    cache.clear()
    ModuleSettings.objects.update_or_create(
        module_name='appraisals',
        defaults={'is_enabled': True, 'description': 'Staff appraisals'},
    )


def _sale(user, total, occurred_at, status='completed'):
    return Sale.objects.create(
        status=status,
        payment_method='cash',
        subtotal=Decimal(str(total)),
        tax_amount=Decimal('0'),
        discount_amount=Decimal('0'),
        total=Decimal(str(total)),
        amount_paid=Decimal(str(total)),
        cashier=user,
        served_by=user,
        occurred_at=occurred_at,
    )


class AppraisalMeAPITests(SalesAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        _enable_appraisals()

    def setUp(self):
        super().setUp()
        _enable_appraisals()
        save_template(default_template())

    def test_sales_sees_own_daily_star_and_progress(self):
        _sale(self.sales_user, 18500, timezone.now())
        response = self.client.get('/api/appraisals/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        today = response.data['today']
        self.assertEqual(today['stars'], 3)
        self.assertEqual(today['amount_to_target'], 1500)
        self.assertEqual(today['tone'], 'amber')
        self.assertTrue(response.data['has_personal_target'])
        self.assertIn('headline', response.data['greeting'])
        self.assertNotIn('Bonus', response.data['greeting']['detail'])
        self.assertEqual(len(response.data['today_tips']['tips']), 5)
        self.assertTrue(response.data['today_tips']['title'])
        self.assertEqual(response.data['year']['basic_pay'], 15000)
        self.assertFalse(response.data['year']['qualifies'])

    def test_holding_sales_do_not_count(self):
        _sale(self.sales_user, 50000, timezone.now(), status='holding')
        response = self.client.get('/api/appraisals/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['today']['stars'], 1)
        self.assertEqual(response.data['today']['sales'], 0)

    def test_field_sales_uses_own_daily_target(self):
        payload = default_template()
        payload['role_daily_targets']['Field Sales'] = 25000
        save_template(payload)
        field = User.objects.create_user('appraisal_field', password='field123')
        UserProfile.objects.create(
            user=field,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_FIELD_AGENT),
            is_active=True,
        )
        _sale(field, 25000, timezone.now())
        token = RefreshToken.for_user(field)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        me = self.client.get('/api/appraisals/me/')
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data['today']['target'], 25000)
        self.assertEqual(me.data['today']['stars'], 4)
        self.assertEqual(me.data['today']['label'], 'TARGET MET')
        self.assertEqual(me.data['policy']['role_daily_targets']['Field Sales'], 25000)
        self.assertEqual(me.data['policy']['role_daily_targets']['Sales Personnel'], 20000)

    def test_sales_cannot_read_team_or_write_policy(self):
        self.assertEqual(self.client.get('/api/appraisals/team/').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.put('/api/appraisals/policy/', {'basic_pay': 20000}, format='json').status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(self.client.get('/api/appraisals/increments/').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.post('/api/appraisals/increments/1/decision/', {'decision': 'approve'}, format='json').status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_admin_can_change_bands(self):
        admin = User.objects.create_superuser('appraisal_admin', 'a@test.com', 'admin123')
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken.for_user(admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        payload = default_template()
        payload['daily_star_bands'] = [
            {'min': 0, 'stars': 1, 'label': ''},
            {'min': 1000, 'stars': 5, 'label': 'FAST TRACK'},
        ]
        payload['basic_pay'] = 16000
        response = self.client.put('/api/appraisals/policy/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['basic_pay'], 16000)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.sales_user).access_token}'
        )
        _sale(self.sales_user, 1000, timezone.now())
        me = self.client.get('/api/appraisals/me/')
        self.assertEqual(me.data['today']['stars'], 5)
        self.assertEqual(me.data['policy']['basic_pay'], 16000)


class AppraisalTeamAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        _enable_appraisals()

    def setUp(self):
        super().setUp()
        _enable_appraisals()
        save_template(default_template())

    def test_manager_sees_own_progress_and_team(self):
        _sale(self.manager_user, 35000, timezone.now())
        me = self.client.get('/api/appraisals/me/')
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data['today']['stars'], 4)
        self.assertEqual(me.data['today']['target'], 35000)
        self.assertEqual(me.data['today']['label'], 'TARGET MET')
        self.assertEqual(me.data['policy']['daily_target'], 20000)
        self.assertEqual(me.data['policy']['manager_daily_target'], 35000)
        applied = me.data['applied_policy']
        self.assertEqual(applied['role'], 'Manager')
        self.assertEqual(applied['daily_target'], 35000)
        bonus_four = next(
            b for b in applied['monthly_bonus_bands'] if abs(float(b['stars']) - 4) < 0.01
        )
        self.assertEqual(bonus_four['min'], 1750000)
        self.assertEqual(bonus_four['bonus'], 2000)
        team = self.client.get('/api/appraisals/team/')
        self.assertEqual(team.status_code, status.HTTP_200_OK)
        names = {row['staff']['id'] for row in team.data['results']}
        self.assertIn(self.manager_user.id, names)
        self.assertIn('insights', team.data)
        self.assertIn('lines', team.data['insights'])

    def test_manager_daily_target_is_configurable(self):
        payload = default_template()
        payload['manager_daily_target'] = 40000
        payload['role_daily_targets']['Manager'] = 40000
        save_template(payload)
        _sale(self.manager_user, 40000, timezone.now())
        me = self.client.get('/api/appraisals/me/')
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data['today']['target'], 40000)
        self.assertEqual(me.data['today']['stars'], 4)
        self.assertEqual(me.data['today']['label'], 'TARGET MET')
        self.assertEqual(me.data['policy']['role_daily_targets']['Manager'], 40000)


class AppraisalPolicyAPITests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        _enable_appraisals()

    def test_get_default_policy(self):
        response = self.client.get('/api/appraisals/policy/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['daily_target'], 20000)
        self.assertEqual(response.data['manager_daily_target'], 35000)
        self.assertEqual(response.data['role_daily_targets']['Manager'], 35000)
        self.assertEqual(response.data['role_daily_targets']['Sales Personnel'], 20000)
        self.assertEqual(response.data['role_daily_targets']['Field Sales'], 20000)
        self.assertEqual(len(response.data['daily_tip_packs']), 5)
        self.assertEqual(len(response.data['daily_tip_packs'][0]['tips']), 5)
        self.assertFalse(response.data['show_year_end_increment'])
        self.assertEqual(response.data['year_end_increment'], 3000)
        self.assertEqual(response.data['working_days'], 26)
        self.assertTrue(response.data['greet_when_no_sticky_notes'])
        self.assertNotIn('Super Admin', response.data['role_daily_targets'])
        self.assertNotIn('Admin', response.data['role_daily_targets'])

    def test_admin_has_no_personal_target(self):
        save_template(default_template())
        _sale(self.admin, 50000, timezone.now())
        me = self.client.get('/api/appraisals/me/')
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertFalse(me.data['has_personal_target'])
        self.assertFalse(me.data['show_on_home'])
        self.assertIsNone(me.data['today'])
        team = self.client.get('/api/appraisals/team/')
        self.assertEqual(team.status_code, status.HTTP_200_OK)
        ids = {row['staff']['id'] for row in team.data['results']}
        self.assertNotIn(self.admin.id, ids)

    def test_rejects_duplicate_daily_bands(self):
        payload = default_template()
        payload['daily_star_bands'] = [
            {'min': 0, 'stars': 1},
            {'min': 0, 'stars': 2},
        ]
        response = self.client.put('/api/appraisals/policy/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_policy_preview_and_versions(self):
        payload = default_template()
        payload['daily_target'] = 25000
        payload['role_daily_targets']['Sales Personnel'] = 25000
        payload['change_reason'] = 'Updated sales expectations'
        payload['effective_from'] = timezone.localdate().isoformat()
        response = self.client.put('/api/appraisals/policy/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['daily_target'], 25000)
        self.assertIn('Sales Personnel', response.data['role_previews'])
        self.assertEqual(response.data['role_previews']['Sales Personnel']['four_star_target'], 25000)
        self.assertTrue(response.data['versions'])
        self.assertEqual(response.data['versions'][-1]['snapshot']['daily_target'], 20000)


class AppraisalIncrementAPITests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        _enable_appraisals()

    def test_admin_can_approve_qualifying_increment(self):
        from appraisals.models import AppraisalSalaryIncrement
        from employees.models import Employee

        sales = User.objects.create_user('inc_sales', email='inc@test.com', password='x')
        Employee.objects.create(
            employee_id='E-INC-1',
            first_name='Ina',
            last_name='Cash',
            email='inc@test.com',
            position='Sales',
            hire_date=timezone.localdate(),
            salary=Decimal('15000'),
        )
        row = AppraisalSalaryIncrement.objects.create(
            user=sales,
            year=2025,
            role_name='Sales Personnel',
            previous_basic=Decimal('15000'),
            increment_amount=Decimal('3000'),
            new_basic=Decimal('18000'),
            qualifies=True,
            status=AppraisalSalaryIncrement.STATUS_PENDING,
        )
        response = self.client.post(
            f'/api/appraisals/increments/{row.id}/decision/',
            {'decision': 'approve', 'reason': 'Year-end review'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'approved')
        row.refresh_from_db()
        self.assertEqual(row.status, 'approved')
        self.assertEqual(Employee.objects.get(email='inc@test.com').salary, Decimal('18000'))


class AppraisalRecalcAPITests(SalesAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        _enable_appraisals()

    def setUp(self):
        super().setUp()
        _enable_appraisals()
        save_template(default_template())

    def test_refund_recalculates_daily_stars(self):
        from sales.models import SaleRefund

        sale = _sale(self.sales_user, 24000, timezone.now())
        me = self.client.get('/api/appraisals/me/')
        self.assertEqual(me.data['today']['stars'], 5)
        SaleRefund.objects.create(
            sale=sale,
            refund_type='partial',
            amount=Decimal('15000'),
            reason='customer return',
            refunded_by=self.sales_user,
        )
        me = self.client.get('/api/appraisals/me/')
        self.assertEqual(me.data['today']['sales'], 9000)
        self.assertEqual(me.data['today']['stars'], 1)

    def test_cancelled_sale_does_not_count(self):
        _sale(self.sales_user, 50000, timezone.now(), status='cancelled')
        me = self.client.get('/api/appraisals/me/')
        self.assertEqual(me.data['today']['sales'], 0)
        self.assertEqual(me.data['today']['stars'], 1)

