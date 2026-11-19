"""One-day leave and sick days: who decides, and who is told."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import UserProfile
from accounts.role_definitions import ensure_permissions, sync_default_roles
from employees.models import LeaveRequest
from messaging.models import MessageOutbox
from settings.models import ModuleFeature, ModuleSettings


class LeaveRequestTests(TestCase):
    """File, approve, reject, and keep phones out of the response."""

    def setUp(self):
        ensure_permissions()
        roles = sync_default_roles()
        module, _ = ModuleSettings.objects.update_or_create(
            module_name='employees',
            defaults={'description': 'Employees', 'is_enabled': True},
        )
        ModuleFeature.objects.update_or_create(
            module=module,
            feature_key='leave_requests',
            defaults={'feature_name': 'Leave', 'is_enabled': True},
        )
        self.sales = self._user('leave_sales', roles['Sales Personnel'], 'cashier', '0718111001')
        self.manager = self._user('leave_manager', roles['Manager'], 'manager', '0718111002')
        self.director = self._user('leave_director', roles['Director'], 'director', '0718111003')
        self.day = timezone.localdate() + timedelta(days=1)

    def _user(self, username, role, legacy, phone):
        user = User.objects.create_user(username, password='secret-pass')
        UserProfile.objects.create(
            user=user,
            role=legacy,
            custom_role=role,
            phone_number=phone,
        )
        return user

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_a_manager_decides_staff_and_directors_are_told(self):
        sales = self._client(self.sales)
        filed = sales.post('/api/employees/leave-requests/', {
            'kind': 'sick',
            'day': self.day.isoformat(),
            'note': 'Fever',
        }, format='json')
        self.assertEqual(filed.status_code, 201, filed.data)
        self.assertEqual(filed.data['status'], 'pending')
        self.assertNotIn('0718111001', str(filed.data))
        asked = MessageOutbox.objects.filter(to_phone='0718111002', template_key='leave_decision')
        self.assertTrue(asked.exists())

        decided = self._client(self.manager).post(
            f"/api/employees/leave-requests/{filed.data['id']}/decide/",
            {'decision': 'approved', 'note': 'Rest'},
            format='json',
        )
        self.assertEqual(decided.status_code, 200, decided.data)
        self.assertEqual(decided.data['status'], 'approved')
        self.assertNotIn('0718111003', str(decided.data))
        told = MessageOutbox.objects.filter(template_key='leave_decision', body__icontains='was approved')
        phones = set(told.values_list('to_phone', flat=True))
        self.assertIn('0718111001', phones)
        self.assertIn('0718111003', phones)

    def test_a_manager_request_goes_to_a_director(self):
        filed = self._client(self.manager).post('/api/employees/leave-requests/', {
            'kind': 'leave',
            'day': self.day.isoformat(),
        }, format='json')
        self.assertEqual(filed.status_code, 201, filed.data)
        blocked = self._client(self.sales).post(
            f"/api/employees/leave-requests/{filed.data['id']}/decide/",
            {'decision': 'approved'},
            format='json',
        )
        self.assertEqual(blocked.status_code, 403)
        self_decide = self._client(self.manager).post(
            f"/api/employees/leave-requests/{filed.data['id']}/decide/",
            {'decision': 'approved'},
            format='json',
        )
        self.assertIn(self_decide.status_code, (403, 400))
        other_manager = self._user('leave_manager_2', self.manager.profile.custom_role, 'manager', '0718111004')
        peer = self._client(other_manager).post(
            f"/api/employees/leave-requests/{filed.data['id']}/decide/",
            {'decision': 'rejected', 'note': 'Busy day'},
            format='json',
        )
        self.assertEqual(peer.status_code, 403, peer.data)
        ok = self._client(self.director).post(
            f"/api/employees/leave-requests/{filed.data['id']}/decide/",
            {'decision': 'rejected', 'note': 'Need you in'},
            format='json',
        )
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertEqual(ok.data['status'], 'rejected')
        again = self._client(self.manager).post('/api/employees/leave-requests/', {
            'kind': 'leave',
            'day': self.day.isoformat(),
        }, format='json')
        self.assertEqual(again.status_code, 201, again.data)

    def test_legacy_director_role_can_decide_and_bad_input_is_refused(self):
        legacy = self._user('leave_legacy_director', None, 'director', '0718111005')
        filed = self._client(self.manager).post('/api/employees/leave-requests/', {
            'kind': 'leave',
            'day': (self.day + timedelta(days=2)).isoformat(),
        }, format='json')
        self.assertEqual(filed.status_code, 201, filed.data)
        decided = self._client(legacy).post(
            f"/api/employees/leave-requests/{filed.data['id']}/decide/",
            {'decision': 'approved'},
            format='json',
        )
        self.assertEqual(decided.status_code, 200, decided.data)

        bad = self._client(self.sales).post('/api/employees/leave-requests/', {
            'kind': 'holiday',
            'day': self.day.isoformat(),
        }, format='json')
        self.assertEqual(bad.status_code, 400, bad.data)
        huge = self._client(self.sales).post('/api/employees/leave-requests/', {
            'kind': 'leave',
            'day': self.day.isoformat(),
            'note': 'x' * 301,
        }, format='json')
        self.assertEqual(huge.status_code, 400, huge.data)
        broken = self._client(self.sales).post('/api/employees/leave-requests/', {
            'kind': 'leave',
            'day': 'tomorrow',
        }, format='json')
        self.assertEqual(broken.status_code, 400, broken.data)
        far = self._client(self.sales).post('/api/employees/leave-requests/', {
            'kind': 'leave',
            'day': (timezone.localdate() + timedelta(days=91)).isoformat(),
        }, format='json')
        self.assertEqual(far.status_code, 400, far.data)
        self.assertFalse(LeaveRequest.objects.filter(user=self.sales, note='x' * 301).exists())

    def test_anonymous_and_a_switched_off_feature_are_blocked(self):
        anonymous = APIClient().get('/api/employees/leave-requests/')
        self.assertEqual(anonymous.status_code, 401)
        from accounts.models import Role

        empty = Role.objects.create(name='Leave None', is_active=True)
        stranger = User.objects.create_user('leave_stranger', password='x')
        UserProfile.objects.create(user=stranger, role='cashier', custom_role=empty)
        denied = self._client(stranger).post('/api/employees/leave-requests/', {
            'kind': 'leave',
            'day': self.day.isoformat(),
        }, format='json')
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn('0718111001', str(denied.data))
        ModuleFeature.objects.filter(feature_key='leave_requests').update(is_enabled=False)
        hidden = self._client(self.sales).get('/api/employees/leave-requests/')
        self.assertEqual(hidden.status_code, 403)

    def test_one_day_off_each_month_until_the_number_changes(self):
        client = self._client(self.sales)
        month_start = (timezone.localdate().replace(day=1) + timedelta(days=32)).replace(day=1)
        first = client.post('/api/employees/leave-requests/', {
            'kind': 'leave',
            'day': month_start.isoformat(),
        }, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        second_day = month_start + timedelta(days=1)
        blocked = client.post('/api/employees/leave-requests/', {
            'kind': 'leave',
            'day': second_day.isoformat(),
        }, format='json')
        self.assertEqual(blocked.status_code, 400, blocked.data)
        self.assertIn('1 day off', str(blocked.data['day']))
        sick = client.post('/api/employees/leave-requests/', {
            'kind': 'sick',
            'day': second_day.isoformat(),
        }, format='json')
        self.assertEqual(sick.status_code, 201, sick.data)

        denied = client.patch('/api/employees/leave-allowance/', {'monthly_leave_days': 2}, format='json')
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn('0718111001', str(denied.data))

        raised = self._client(self.manager).patch(
            '/api/employees/leave-allowance/',
            {'monthly_leave_days': 2},
            format='json',
        )
        self.assertEqual(raised.status_code, 200, raised.data)
        self.assertEqual(raised.data['shop_days'], 2)
        opened = client.post('/api/employees/leave-requests/', {
            'kind': 'leave',
            'day': (month_start + timedelta(days=2)).isoformat(),
        }, format='json')
        self.assertEqual(opened.status_code, 201, opened.data)

        other = self._user('leave_sales_2', self.sales.profile.custom_role, 'cashier', '0718111009')
        personal = self._client(self.director).patch('/api/employees/leave-allowance/', {
            'user_id': other.id,
            'monthly_leave_days': 0,
        }, format='json')
        self.assertEqual(personal.status_code, 200, personal.data)
        self.assertEqual(personal.data['effective'], 0)
        none = self._client(other).post('/api/employees/leave-requests/', {
            'kind': 'leave',
            'day': month_start.isoformat(),
        }, format='json')
        self.assertEqual(none.status_code, 400, none.data)
        cleared = self._client(self.director).patch('/api/employees/leave-allowance/', {
            'user_id': other.id,
            'monthly_leave_days': None,
        }, format='json')
        self.assertEqual(cleared.status_code, 200, cleared.data)
        self.assertIsNone(cleared.data['monthly_leave_days'])
        self.assertEqual(cleared.data['effective'], 2)
        bad = self._client(self.manager).patch(
            '/api/employees/leave-allowance/',
            {'monthly_leave_days': 40},
            format='json',
        )
        self.assertEqual(bad.status_code, 400, bad.data)

    def test_thirty_days_can_be_requested(self):
        self._client(self.manager).patch(
            '/api/employees/leave-allowance/',
            {'monthly_leave_days': 31},
            format='json',
        )
        client = self._client(self.sales)
        start = timezone.localdate() + timedelta(days=1)
        for offset in range(30):
            response = client.post('/api/employees/leave-requests/', {
                'kind': 'leave',
                'day': (start + timedelta(days=offset)).isoformat(),
            }, format='json')
            self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(LeaveRequest.objects.filter(user=self.sales).count(), 30)
        listing = client.get('/api/employees/leave-requests/')
        self.assertEqual(listing.status_code, 200)
        self.assertGreaterEqual(len(listing.data['results']), 30)
        self.assertNotIn('0718111001', str(listing.data))
