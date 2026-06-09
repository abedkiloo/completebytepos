"""Unit tests for sales person report period parsing."""

from datetime import datetime

from django.test import RequestFactory, TestCase
from django.utils import timezone

from reports.sales_person_report import resolve_sales_person_period


class SalesPersonPeriodTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_month_param(self):
        request = self.factory.get('/api/reports/sales_by_person/', {'month': '2025-05'})
        start, end, label = resolve_sales_person_period(request)
        self.assertEqual(label, '2025-05')
        self.assertEqual(start, timezone.make_aware(datetime(2025, 5, 1)))
        self.assertEqual(end.month, 5)
        self.assertEqual(end.day, 31)

    def test_invalid_month_falls_back(self):
        request = self.factory.get('/api/reports/sales_by_person/', {'month': 'bad'})
        start, end, label = resolve_sales_person_period(request)
        self.assertNotEqual(label, 'bad')
