"""Planned maps: polyline, depot, geometry cache, staff/driver APIs."""

import urllib.error
from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework import serializers, status

from delivery.maps.access import (
    user_may_view_agent_route,
    user_may_view_delivery_history,
    user_may_view_route_on_date,
)
from delivery.maps.config import configured_secret, maps_public_config, maps_server_key
from delivery.maps.geometry import (
    SOURCE_GOOGLE,
    SOURCE_STRAIGHT,
    _coord,
    build_route_geometry,
    empty_geometry,
    geometry_fingerprint,
    invalidate_route_geometry,
    resolve_depot,
)
from delivery.maps.google_routes import (
    ROUTES_URL,
    fetch_encoded_polyline,
    post_json,
    routes_request_body,
)
from delivery.maps.polyline import decode_polyline, encode_polyline
from delivery.models import DeliveryRoute
from delivery.tests.test_delivery import DeliveryAPITestCase
from settings.models import Branch, Tenant
from settings.serializers import BranchSerializer


class PolylineTests(SimpleTestCase):
    def test_google_sample_roundtrip(self):
        points = [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]
        encoded = encode_polyline(points)
        self.assertEqual(encoded, '_p~iF~ps|U_ulLnnqC_mqNvxq`@')
        decoded = decode_polyline(encoded)
        self.assertEqual(len(decoded), 3)
        for got, expected in zip(decoded, points):
            self.assertAlmostEqual(got[0], expected[0], places=4)
            self.assertAlmostEqual(got[1], expected[1], places=4)

    def test_empty_and_truncated(self):
        self.assertEqual(decode_polyline(''), [])
        self.assertEqual(encode_polyline([]), '')
        # Truncated payload should not raise.
        decode_polyline('_p')


class MapsConfigTests(SimpleTestCase):
    def test_configured_secret_rejects_placeholders(self):
        self.assertEqual(configured_secret(''), '')
        self.assertEqual(configured_secret('  REPLACE_WITH_MAPS_SERVER_KEY  '), '')
        self.assertEqual(configured_secret('your-key-here'), '')
        self.assertEqual(configured_secret('change-me'), '')
        self.assertEqual(configured_secret('AIzaSyRealKey123'), 'AIzaSyRealKey123')

    @override_settings(GOOGLE_MAPS_SERVER_KEY='REPLACE_WITH_MAPS_SERVER_KEY')
    def test_placeholder_server_key_is_inactive(self):
        self.assertEqual(maps_server_key(), '')
        cfg = maps_public_config()
        self.assertFalse(cfg['routes_api_configured'])
        self.assertFalse(cfg['live_tracking_enabled'])
        self.assertEqual(cfg['default_depot']['latitude'], -1.2921)

    @override_settings(GOOGLE_MAPS_SERVER_KEY='AIzaSyRealKey123')
    def test_real_server_key_is_active(self):
        self.assertEqual(maps_server_key(), 'AIzaSyRealKey123')
        self.assertTrue(maps_public_config()['routes_api_configured'])


class AccessTests(SimpleTestCase):
    def test_viewer_rules(self):
        self.assertFalse(user_may_view_agent_route(None, 1))
        anon = MagicMock(is_authenticated=False, id=1)
        self.assertFalse(user_may_view_agent_route(anon, 1))
        self.assertFalse(user_may_view_agent_route(MagicMock(is_authenticated=True, id=1), 'x'))

        own = MagicMock(is_authenticated=True, id=9, is_superuser=False, profile=None)
        self.assertTrue(user_may_view_agent_route(own, 9))

        su = MagicMock(is_authenticated=True, id=1, is_superuser=True, profile=None)
        self.assertTrue(user_may_view_agent_route(su, 99))

        none = MagicMock(is_authenticated=True, id=1, is_superuser=False, profile=None)
        self.assertFalse(user_may_view_agent_route(none, 99))

        mgr = MagicMock(is_authenticated=True, id=1, is_superuser=False)
        mgr.profile.is_super_admin = False
        mgr.profile.is_manager = True
        self.assertTrue(user_may_view_agent_route(mgr, 99))

        dispatch = MagicMock(is_authenticated=True, id=1, is_superuser=False)
        dispatch.profile.is_super_admin = False
        dispatch.profile.is_manager = False
        dispatch.profile.has_permission.return_value = True
        self.assertTrue(user_may_view_agent_route(dispatch, 99))
        dispatch.profile.has_permission.assert_called_with('dispatch', 'view')

        sales = MagicMock(is_authenticated=True, id=1, is_superuser=False)
        sales.profile.is_super_admin = False
        sales.profile.is_manager = False
        sales.profile.has_permission.return_value = False
        self.assertFalse(user_may_view_agent_route(sales, 99))

        admin = MagicMock(is_authenticated=True, id=2, is_superuser=False)
        admin.profile.is_super_admin = True
        admin.profile.is_manager = False
        self.assertTrue(user_may_view_agent_route(admin, 99))

    def test_history_and_past_date_rules(self):
        from datetime import timedelta

        class Role:
            def __init__(self, name):
                self.name = name

        self.assertFalse(user_may_view_delivery_history(None))
        anon = MagicMock(is_authenticated=False)
        self.assertFalse(user_may_view_delivery_history(anon))

        su = MagicMock(is_authenticated=True, is_superuser=True, profile=None)
        self.assertTrue(user_may_view_delivery_history(su))

        none = MagicMock(is_authenticated=True, is_superuser=False, profile=None)
        self.assertFalse(user_may_view_delivery_history(none))

        admin = MagicMock(is_authenticated=True, is_superuser=False)
        admin.profile.is_super_admin = True
        admin.profile.has_permission.return_value = False
        admin.profile.custom_role = None
        admin.profile.role = 'cashier'
        self.assertTrue(user_may_view_delivery_history(admin))

        mgr = MagicMock(is_authenticated=True, is_superuser=False, id=1)
        mgr.profile.is_super_admin = False
        mgr.profile.is_manager = True
        mgr.profile.has_permission.return_value = False
        mgr.profile.custom_role = Role('Manager')
        mgr.profile.role = 'manager'
        self.assertTrue(user_may_view_delivery_history(mgr))

        disp = MagicMock(is_authenticated=True, is_superuser=False, id=1)
        disp.profile.is_super_admin = False
        disp.profile.is_manager = True
        disp.profile.has_permission.return_value = False
        disp.profile.custom_role = Role('Dispatcher')
        disp.profile.role = 'manager'
        self.assertFalse(user_may_view_delivery_history(disp))

        granted = MagicMock(is_authenticated=True, is_superuser=False, id=1)
        granted.profile.is_super_admin = False
        granted.profile.is_manager = False
        granted.profile.custom_role = Role('Ops Lead')
        granted.profile.role = 'cashier'

        def _hist(module, action):
            return module == 'delivery' and action == 'history'

        granted.profile.has_permission.side_effect = _hist
        self.assertTrue(user_may_view_delivery_history(granted))

        legacy = MagicMock(is_authenticated=True, is_superuser=False)
        legacy.profile.is_super_admin = False
        legacy.profile.has_permission.return_value = False
        legacy.profile.custom_role = None
        legacy.profile.role = 'admin'
        self.assertTrue(user_may_view_delivery_history(legacy))

        nameless = MagicMock(is_authenticated=True, is_superuser=False)
        nameless.profile.is_super_admin = False
        nameless.profile.has_permission.return_value = False
        nameless.profile.custom_role = object()
        nameless.profile.role = 'cashier'
        self.assertFalse(user_may_view_delivery_history(nameless))

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        self.assertTrue(user_may_view_route_on_date(disp, 99, today))
        self.assertTrue(user_may_view_route_on_date(disp, 99, None))
        self.assertFalse(user_may_view_route_on_date(disp, 99, yesterday))
        self.assertTrue(user_may_view_route_on_date(mgr, 99, yesterday))
        sales = MagicMock(is_authenticated=True, is_superuser=False, id=4)
        sales.profile.is_super_admin = False
        sales.profile.is_manager = False
        sales.profile.has_permission.return_value = False
        self.assertFalse(user_may_view_route_on_date(sales, 99, today))
        own = MagicMock(is_authenticated=True, is_superuser=False, id=9, profile=None)
        self.assertFalse(user_may_view_route_on_date(own, 9, yesterday))
        self.assertTrue(user_may_view_route_on_date(own, 9, today))


class GoogleRoutesTests(SimpleTestCase):
    def test_request_body_and_fetch_guards(self):
        body = routes_request_body((1, 2), (3, 4), [(5, 6)])
        self.assertEqual(body['origin']['location']['latLng']['latitude'], 1)
        self.assertEqual(len(body['intermediates']), 1)
        self.assertIsNone(fetch_encoded_polyline([(1, 2)], api_key='k'))
        self.assertIsNone(fetch_encoded_polyline([(1, 2), (3, 4)], api_key=''))

    def test_fetch_success_and_failures(self):
        def ok(url, payload, headers, timeout=8):
            self.assertEqual(url, ROUTES_URL)
            self.assertIn('X-Goog-Api-Key', headers)
            self.assertEqual(payload['travelMode'], 'DRIVE')
            return {'routes': [{'polyline': {'encodedPolyline': 'abc'}}]}

        self.assertEqual(
            fetch_encoded_polyline([(1, 2), (3, 4), (5, 6)], api_key='k', post=ok),
            'abc',
        )
        self.assertIsNone(
            fetch_encoded_polyline(
                [(1, 2), (3, 4)],
                api_key='k',
                post=lambda *a, **k: {'routes': []},
            ),
        )
        self.assertIsNone(
            fetch_encoded_polyline(
                [(1, 2), (3, 4)],
                api_key='k',
                post=lambda *a, **k: {'routes': [{'polyline': {}}]},
            ),
        )
        self.assertIsNone(
            fetch_encoded_polyline(
                [(1, 2), (3, 4)],
                api_key='k',
                post=lambda *a, **k: [],
            ),
        )

        def boom(*a, **k):
            raise urllib.error.URLError('offline')

        self.assertIsNone(fetch_encoded_polyline([(1, 2), (3, 4)], api_key='k', post=boom))

    def test_post_json_reads_body(self):
        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"ok": true}'

        with patch('delivery.maps.google_routes.urllib.request.urlopen', return_value=FakeResp()):
            self.assertEqual(post_json('http://example.test', {'a': 1}, {'H': '1'}), {'ok': True})


class BranchPinSerializerTests(SimpleTestCase):
    def test_lat_lng_bounds(self):
        ser = BranchSerializer()
        self.assertIsNone(ser.validate_latitude(''))
        self.assertIsNone(ser.validate_longitude(None))
        self.assertEqual(ser.validate_latitude(-1.3), -1.3)
        with self.assertRaises(serializers.ValidationError):
            ser.validate_latitude(99)
        with self.assertRaises(serializers.ValidationError):
            ser.validate_longitude(-200)


class MapsGeometryAPITests(DeliveryAPITestCase):
    def _tenant_branch(self, **coords):
        tenant = Tenant.objects.create(
            name='Maps Co',
            code='MAPS',
            country='Kenya',
            owner=self.driver,
            created_by=self.driver,
        )
        return Branch.objects.create(
            tenant=tenant,
            branch_code='HQ1',
            name='Westlands shop',
            is_active=True,
            is_headquarters=True,
            created_by=self.driver,
            **coords,
        )

    def test_coord_helpers_and_placeholder_depot(self):
        self.assertIsNone(_coord(None))
        self.assertIsNone(_coord(''))
        self.assertIsNone(_coord('nope'))
        self.assertAlmostEqual(_coord('-1.30'), -1.30)
        depot = resolve_depot(None)
        self.assertTrue(depot['placeholder'])
        self.assertEqual(depot['latitude'], -1.2921)
        empty = empty_geometry(self.driver.id, date(2026, 9, 24), agent=self.driver)
        self.assertIsNone(empty['route_id'])
        self.assertEqual(empty['stops'], [])
        self.assertEqual(empty['path'][0]['latitude'], -1.2921)
        nameless = empty_geometry(9, date(2026, 9, 24), agent=None)
        self.assertEqual(nameless['delivery_agent_name'], '')

    def test_depot_from_headquarters_pin(self):
        self._tenant_branch(latitude='-1.2500', longitude='36.8000')
        depot = resolve_depot(None)
        self.assertFalse(depot['placeholder'])
        self.assertEqual(depot['label'], 'Westlands shop')
        self.assertAlmostEqual(depot['latitude'], -1.25)

    def test_named_hq_without_pin_still_placeholder(self):
        self._tenant_branch()
        depot = resolve_depot(None)
        self.assertTrue(depot['placeholder'])
        self.assertEqual(depot['label'], 'Westlands shop')

    def test_driver_today_geometry_straight_line(self):
        self._ready_order()
        self._auth(self.driver)
        res = self.client.get('/api/delivery/routes/today/geometry/')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data['source'], SOURCE_STRAIGHT)
        self.assertTrue(res.data['encoded_polyline'])
        self.assertEqual(len(res.data['stops']), 1)
        self.assertAlmostEqual(float(res.data['stops'][0]['latitude']), -1.30)
        self.assertGreaterEqual(len(res.data['path']), 2)
        cfg = self.client.get('/api/delivery/config/')
        self.assertFalse(cfg.data['maps']['routes_api_configured'])
        self.assertFalse(cfg.data['maps']['can_view_history'])

        # Cached: second read does not need Google.
        again = self.client.get('/api/delivery/routes/today/geometry/')
        self.assertEqual(again.data['encoded_polyline'], res.data['encoded_polyline'])

    def test_staff_geometry_and_permissions(self):
        self._ready_order()
        self._auth(self.dispatch)
        missing = self.client.get('/api/delivery/routes/geometry/')
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        bad_id = self.client.get('/api/delivery/routes/geometry/', {'agent_id': 'x'})
        self.assertEqual(bad_id.status_code, status.HTTP_400_BAD_REQUEST)
        bad_date = self.client.get(
            '/api/delivery/routes/geometry/',
            {'agent_id': self.driver.id, 'date': 'not-a-date'},
        )
        self.assertEqual(bad_date.status_code, status.HTTP_400_BAD_REQUEST)

        ok = self.client.get(
            '/api/delivery/routes/geometry/',
            {'agent_id': self.driver.id},
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK, ok.data)
        self.assertEqual(ok.data['delivery_agent_id'], self.driver.id)
        self.assertEqual(len(ok.data['stops']), 1)

        empty = self.client.get(
            '/api/delivery/routes/geometry/',
            {'agent_id': self.driver2.id, 'date': '2099-01-01'},
        )
        self.assertEqual(empty.status_code, status.HTTP_200_OK)
        self.assertIsNone(empty.data['route_id'])

        self._auth(self.sales)
        forbidden = self.client.get(
            '/api/delivery/routes/geometry/',
            {'agent_id': self.driver.id},
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        self._auth(self.driver)
        own = self.client.get(
            '/api/delivery/routes/geometry/',
            {'agent_id': self.driver.id},
        )
        self.assertEqual(own.status_code, status.HTTP_200_OK)

    def test_google_success_then_cache_and_fallback(self):
        self._ready_order()
        route = DeliveryRoute.objects.get(
            delivery_agent=self.driver, route_date=timezone.localdate(),
        )
        fake = encode_polyline([(-1.2921, 36.8219), (-1.30, 36.80)])
        with override_settings(GOOGLE_MAPS_SERVER_KEY='AIzaSyTestRoutesKey'), patch(
            'delivery.maps.geometry.fetch_encoded_polyline',
            return_value=fake,
        ) as mocked:
            payload = build_route_geometry(route)
            self.assertEqual(payload['source'], SOURCE_GOOGLE)
            self.assertEqual(payload['encoded_polyline'], fake)
            mocked.assert_called_once()
            build_route_geometry(route)
            mocked.assert_called_once()

        route.refresh_from_db()
        invalidate_route_geometry(route)
        route.refresh_from_db()
        self.assertEqual(route.encoded_polyline, '')

        with override_settings(GOOGLE_MAPS_SERVER_KEY='AIzaSyTestRoutesKey'), patch(
            'delivery.maps.geometry.fetch_encoded_polyline',
            return_value=None,
        ):
            payload = build_route_geometry(route)
            self.assertEqual(payload['source'], SOURCE_STRAIGHT)

    def test_new_stop_invalidates_polyline(self):
        self._ready_order()
        route = DeliveryRoute.objects.get(
            delivery_agent=self.driver, route_date=timezone.localdate(),
        )
        route.encoded_polyline = 'cached'
        route.polyline_source = SOURCE_STRAIGHT
        route.geometry_fingerprint = 'old'
        route.save()
        self._ready_order()
        route.refresh_from_db()
        self.assertEqual(route.encoded_polyline, '')
        self.assertEqual(route.geometry_fingerprint, '')

    def test_stop_without_pin_is_listed(self):
        order = self._ready_order()
        site = order.site
        site.latitude = None
        site.longitude = None
        site.label = ''
        site.save(update_fields=['latitude', 'longitude', 'label'])
        route = DeliveryRoute.objects.get(
            delivery_agent=self.driver, route_date=timezone.localdate(),
        )
        payload = build_route_geometry(route)
        self.assertEqual(len(payload['stops']), 1)
        self.assertIsNone(payload['stops'][0]['latitude'])
        self.assertEqual(payload['stops'][0]['label'], 'Del Cust')
        self.assertEqual(payload['encoded_polyline'], '')

    def test_fingerprint_changes_with_routes_flag(self):
        depot = {'latitude': -1.2, 'longitude': 36.8, 'placeholder': False}
        a = geometry_fingerprint(depot, [(1, -1.3, 36.8)], routes_configured=False)
        b = geometry_fingerprint(depot, [(1, -1.3, 36.8)], routes_configured=True)
        self.assertNotEqual(a, b)

    def test_rebuild_when_cached_polyline_cleared(self):
        self._ready_order()
        route = DeliveryRoute.objects.get(
            delivery_agent=self.driver, route_date=timezone.localdate(),
        )
        build_route_geometry(route)
        route.refresh_from_db()
        self.assertTrue(route.encoded_polyline)
        route.encoded_polyline = ''
        route.save(update_fields=['encoded_polyline'])
        payload = build_route_geometry(route)
        self.assertTrue(payload['encoded_polyline'])

    def test_empty_decoded_path_falls_back_to_depot(self):
        self._ready_order()
        route = DeliveryRoute.objects.get(
            delivery_agent=self.driver, route_date=timezone.localdate(),
        )
        build_route_geometry(route)
        route.encoded_polyline = ''
        route.save(update_fields=['encoded_polyline'])
        with patch('delivery.maps.geometry._waypoints', return_value=[]):
            payload = build_route_geometry(route)
        self.assertEqual(
            payload['path'][0]['latitude'],
            payload['depot']['latitude'],
        )
