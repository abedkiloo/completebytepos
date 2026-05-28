"""Unit tests for reports.views.resolve_period."""

from datetime import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from reports.services import resolve_period


class ResolvePeriodTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _get(self, params=None):
        wsgi = self.factory.get('/api/reports/sales_overview/', params or {})
        return resolve_period(Request(wsgi))

    def test_today_period(self):
        start, end, label = self._get({'period': 'today'})
        self.assertEqual(label, 'today')
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertLess(start, end)

    def test_week_period(self):
        start, end, label = self._get({'period': 'week'})
        self.assertEqual(label, 'week')
        self.assertIsNotNone(start)

    def test_month_period(self):
        start, end, label = self._get({'period': 'month'})
        self.assertEqual(label, 'month')
        today = timezone.now().date()
        self.assertEqual(start.date().day, 1)
        self.assertEqual(start.date().month, today.month)

    def test_year_period(self):
        start, end, label = self._get({'period': 'year'})
        self.assertEqual(label, 'year')
        self.assertEqual(start.month, 1)

    def test_custom_date_from_to(self):
        start, end, label = self._get({'date_from': '2025-01-01', 'date_to': '2025-01-31'})
        self.assertEqual(label, 'custom')
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertEqual(start.date(), datetime(2025, 1, 1).date())

    def test_invalid_date_from_ignored(self):
        start, end, label = self._get({'date_from': 'not-a-date'})
        self.assertEqual(label, 'custom')
        self.assertIsNone(start)

    def test_unknown_period_falls_back_to_custom(self):
        start, end, label = self._get({'period': 'quarter'})
        self.assertEqual(label, 'custom')
        self.assertIsNone(start)
        self.assertIsNone(end)
