"""Past delivery routes: manager/admin + delivery.history."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import status

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER
from delivery.models import DeliveryRoute, DeliveryStop
from delivery.serializers import _agent_display_name
from delivery.tests.test_delivery import DeliveryAPITestCase


class DeliveryHistoryAPITests(DeliveryAPITestCase):
    def _manager(self):
        user = User.objects.create_user('hist_mgr', password='x')
        UserProfile.objects.create(
            user=user,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
            is_active=True,
        )
        return user

    def _history_clerk(self):
        role = Role.objects.create(name='History Clerk', is_active=True)
        role.permissions.add(
            Permission.objects.get(module='delivery', action='history'),
            Permission.objects.get(module='dispatch', action='view'),
        )
        user = User.objects.create_user('hist_clerk', password='x')
        UserProfile.objects.create(
            user=user,
            role='cashier',
            custom_role=role,
            is_active=True,
        )
        return user

    def _move_today_route_to_yesterday(self):
        self._ready_order()
        yesterday = timezone.localdate() - timedelta(days=1)
        route = DeliveryRoute.objects.get(
            delivery_agent=self.driver,
            route_date=timezone.localdate(),
        )
        route.route_date = yesterday
        route.save(update_fields=['route_date'])
        stop = route.stops.first()
        stop.status = DeliveryStop.STATUS_COMPLETED
        stop.collection_method = 'cash'
        stop.collection_amount = '400.00'
        stop.save()
        return route, yesterday

    def test_dispatcher_cannot_open_past_geometry(self):
        route, yesterday = self._move_today_route_to_yesterday()
        self._auth(self.dispatch)
        forbidden = self.client.get(
            '/api/delivery/routes/geometry/',
            {'agent_id': self.driver.id, 'date': str(yesterday)},
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)
        lookup = self.client.get(
            '/api/delivery/routes/lookup/',
            {'agent_id': self.driver.id, 'date': str(yesterday)},
        )
        self.assertEqual(lookup.status_code, status.HTTP_403_FORBIDDEN)
        today = self.client.get(
            '/api/delivery/routes/geometry/',
            {'agent_id': self.driver.id},
        )
        self.assertEqual(today.status_code, status.HTTP_200_OK)
        retrieve = self.client.get(f'/api/delivery/routes/{route.id}/')
        self.assertEqual(retrieve.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_lists_and_opens_past_deliveries(self):
        route, yesterday = self._move_today_route_to_yesterday()
        manager = self._manager()
        self._auth(manager)
        listed = self.client.get(
            '/api/delivery/routes/',
            {
                'agent_id': self.driver.id,
                'date_from': str(yesterday),
                'date_to': str(yesterday),
            },
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK, listed.data)
        self.assertEqual(len(listed.data), 1)
        self.assertEqual(listed.data[0]['id'], route.id)
        self.assertEqual(listed.data[0]['stop_count'], 1)
        self.assertEqual(listed.data[0]['completed_count'], 1)
        everyone = self.client.get('/api/delivery/routes/')
        self.assertEqual(everyone.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(everyone.data), 1)

        geo = self.client.get(
            '/api/delivery/routes/geometry/',
            {'agent_id': self.driver.id, 'date': str(yesterday)},
        )
        self.assertEqual(geo.status_code, status.HTTP_200_OK, geo.data)
        self.assertEqual(geo.data['route_id'], route.id)

        lookup = self.client.get(
            '/api/delivery/routes/lookup/',
            {'agent_id': self.driver.id, 'date': str(yesterday)},
        )
        self.assertEqual(lookup.status_code, status.HTTP_200_OK, lookup.data)
        self.assertEqual(lookup.data['id'], route.id)
        self.assertEqual(lookup.data['stops'][0]['status'], 'completed')
        self.assertEqual(lookup.data['stops'][0]['customer_name'], 'Del Cust')

        detail = self.client.get(f'/api/delivery/routes/{route.id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data['delivery_agent_id'], self.driver.id)

        cfg = self.client.get('/api/delivery/config/')
        self.assertTrue(cfg.data['maps']['can_view_history'])

    def test_driver_cannot_list_others_or_own_past(self):
        route, yesterday = self._move_today_route_to_yesterday()
        self._auth(self.driver)
        listed = self.client.get(
            '/api/delivery/routes/',
            {'agent_id': self.driver2.id},
        )
        self.assertEqual(listed.status_code, status.HTTP_403_FORBIDDEN)
        past = self.client.get(
            '/api/delivery/routes/',
            {'date_from': str(yesterday)},
        )
        self.assertEqual(past.status_code, status.HTTP_403_FORBIDDEN)
        own_today = self.client.get('/api/delivery/routes/')
        self.assertEqual(own_today.status_code, status.HTTP_200_OK)
        self.assertEqual(own_today.data, [])
        cfg = self.client.get('/api/delivery/config/')
        self.assertFalse(cfg.data['maps']['can_view_history'])
        retrieve = self.client.get(f'/api/delivery/routes/{route.id}/')
        self.assertEqual(retrieve.status_code, status.HTTP_403_FORBIDDEN)

    def test_history_permission_without_manager_role(self):
        route, yesterday = self._move_today_route_to_yesterday()
        clerk = self._history_clerk()
        self._auth(clerk)
        lookup = self.client.get(
            '/api/delivery/routes/lookup/',
            {'agent_id': self.driver.id, 'date': str(yesterday)},
        )
        self.assertEqual(lookup.status_code, status.HTTP_200_OK, lookup.data)
        self.assertEqual(lookup.data['id'], route.id)

    def test_lookup_empty_and_validation(self):
        manager = self._manager()
        self._auth(manager)
        empty = self.client.get(
            '/api/delivery/routes/lookup/',
            {'agent_id': self.driver.id, 'date': '2099-01-01'},
        )
        self.assertEqual(empty.status_code, status.HTTP_200_OK)
        self.assertIsNone(empty.data['id'])
        self.assertEqual(empty.data['stops'], [])

        missing = self.client.get('/api/delivery/routes/lookup/')
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        bad_id = self.client.get('/api/delivery/routes/lookup/', {'agent_id': 'x'})
        self.assertEqual(bad_id.status_code, status.HTTP_400_BAD_REQUEST)
        bad_date = self.client.get(
            '/api/delivery/routes/lookup/',
            {'agent_id': self.driver.id, 'date': 'nope'},
        )
        self.assertEqual(bad_date.status_code, status.HTTP_400_BAD_REQUEST)

        listed = self.client.get('/api/delivery/routes/', {'agent_id': 'zz'})
        self.assertEqual(listed.status_code, status.HTTP_400_BAD_REQUEST)
        bad_from = self.client.get('/api/delivery/routes/', {'date_from': 'nope'})
        self.assertEqual(bad_from.status_code, status.HTTP_400_BAD_REQUEST)
        bad_to = self.client.get('/api/delivery/routes/', {'date_to': 'nope'})
        self.assertEqual(bad_to.status_code, status.HTTP_400_BAD_REQUEST)

        missing_route = self.client.get('/api/delivery/routes/999999/')
        self.assertEqual(missing_route.status_code, status.HTTP_404_NOT_FOUND)

    def test_sales_cannot_list_other_drivers(self):
        self._auth(self.sales)
        listed = self.client.get(
            '/api/delivery/routes/',
            {'agent_id': self.driver.id},
        )
        self.assertEqual(listed.status_code, status.HTTP_403_FORBIDDEN)
        all_routes = self.client.get('/api/delivery/routes/')
        self.assertEqual(all_routes.status_code, status.HTTP_200_OK)
        self.assertEqual(all_routes.data, [])


class AgentDisplayNameTests(SimpleTestCase):
    def test_missing_and_unnamed_agents(self):
        self.assertEqual(_agent_display_name(None), '')

        class Agent:
            def get_full_name(self):
                return ''

            username = 'driver1'

        self.assertEqual(_agent_display_name(Agent()), 'driver1')
