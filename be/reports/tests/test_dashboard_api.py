"""Legacy dashboard tests — extended coverage lives in test_views.py."""

from rest_framework import status
from rest_framework.test import APIClient

from reports.tests.test_views import ReportsViewsTestCase


class DashboardAPITestCase(ReportsViewsTestCase):
    """Kept for backwards compatibility with earlier phase-1 file."""

    def test_dashboard_returns_payload_for_manager(self):
        response = self.client.get('/api/reports/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('today', response.data)

    def test_dashboard_requires_auth(self):
        anon = APIClient()
        response = anon.get('/api/reports/dashboard/')
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
