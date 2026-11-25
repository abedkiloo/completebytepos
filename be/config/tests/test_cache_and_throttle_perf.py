"""
Unit / module / security tests for scale-oriented cache and throttle wiring.
"""
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from config.cache import build_caches
from accounts.throttles import (
    HeavyReadRateThrottle,
    LoginRateThrottle,
    ReportRateThrottle,
)
from utils.pagination import StandardResultsSetPagination, _max_page_size


class CacheBuilderUnitTests(SimpleTestCase):
    def test_default_is_locmem(self):
        caches = build_caches(running_tests=True)
        self.assertIn('locmem', caches['default']['BACKEND'].lower())

    def test_redis_url_hook_still_works_when_set_later(self):
        """Hook kept for a future Redis adoption; LocMem is the active path."""
        import os

        os.environ['REDIS_URL'] = 'redis://127.0.0.1:6379/1'
        try:
            caches = build_caches(running_tests=False)
            self.assertIn('redis', caches['default']['BACKEND'].lower())
            self.assertEqual(caches['default']['LOCATION'], 'redis://127.0.0.1:6379/1')
        finally:
            os.environ.pop('REDIS_URL', None)

    def test_tests_and_default_path_stay_locmem(self):
        import os

        os.environ.pop('REDIS_URL', None)
        caches = build_caches(running_tests=False)
        self.assertIn('locmem', caches['default']['BACKEND'].lower())
        os.environ['REDIS_URL'] = 'redis://127.0.0.1:6379/1'
        try:
            caches_test = build_caches(running_tests=True)
            self.assertIn('locmem', caches_test['default']['BACKEND'].lower())
        finally:
            os.environ.pop('REDIS_URL', None)


class PaginationCapUnitTests(SimpleTestCase):
    def test_max_page_size_clamps(self):
        import os

        os.environ['API_MAX_PAGE_SIZE'] = '9999'
        try:
            self.assertEqual(_max_page_size(), 500)
        finally:
            os.environ.pop('API_MAX_PAGE_SIZE', None)

    def test_pagination_class_has_cap(self):
        self.assertGreaterEqual(StandardResultsSetPagination.max_page_size, 20)
        self.assertLessEqual(StandardResultsSetPagination.max_page_size, 500)


class ThrottleScopeUnitTests(SimpleTestCase):
    def test_scopes_are_distinct_and_named(self):
        self.assertEqual(LoginRateThrottle.scope, 'login')
        self.assertEqual(ReportRateThrottle.scope, 'reports')
        self.assertEqual(HeavyReadRateThrottle.scope, 'heavy_read')


class ReportThrottleModuleTests(TestCase):
    """Reports use ReportRateThrottle; anonymous still 401 (security)."""

    def test_anonymous_product_trends_denied(self):
        client = APIClient()
        response = client.get('/api/reports/product-trends/', {'product_id': 1})
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        body = str(response.data).lower()
        self.assertNotIn('traceback', body)
        self.assertNotIn('password', body)


class ReportCacheCorrectedTests(TestCase):
    def test_cache_set_get_roundtrip_for_trends_payload(self):
        payload = {'product_id': 7, 'periods': [], 'insights': []}
        cache.set('product_trends:v1:test', payload, 20)
        got = cache.get('product_trends:v1:test')
        self.assertEqual(got['product_id'], 7)
        cache.delete('product_trends:v1:test')
