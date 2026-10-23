"""Unit tests for sales person report period parsing."""

from datetime import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.utils import timezone

from reports.sales_person_report import (
    SalesPersonReportService,
    _display_name,
    resolve_sales_person_period,
)


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

    def test_month_out_of_range_and_december(self):
        bad = self.factory.get('/api/reports/sales_by_person/', {'month': '2025-13'})
        _, _, label = resolve_sales_person_period(bad)
        self.assertNotEqual(label, '2025-13')

        dec = self.factory.get('/api/reports/sales_by_person/', {'month': '2024-12'})
        start, end, label = resolve_sales_person_period(dec)
        self.assertEqual(label, '2024-12')
        self.assertEqual(start.month, 12)
        self.assertEqual(end.year, 2024)
        self.assertEqual(end.month, 12)
        self.assertEqual(end.day, 31)

    def test_custom_period_label_and_display_name(self):
        self.assertEqual(_display_name(None), 'Unassigned')
        user = User(username='cashier1', first_name='', last_name='')
        self.assertEqual(_display_name(user), 'cashier1')

        request = self.factory.get(
            '/api/reports/sales_by_person/',
            {'start': '2025-01-01', 'end': '2025-01-31'},
        )
        with patch(
            'reports.sales_person_report.resolve_period',
            return_value=(
                timezone.make_aware(datetime(2025, 1, 1)),
                timezone.make_aware(datetime(2025, 1, 31, 23, 59, 59)),
                'custom',
            ),
        ):
            _, _, label = resolve_sales_person_period(request)
        self.assertIn('2025-01-01', label)

    def test_build_handles_bad_cashier_and_period_display(self):
        request = self.factory.get(
            '/api/reports/sales_by_person/',
            {'month': '2025-05', 'cashier_id': 'not-int'},
        )
        payload = SalesPersonReportService.build(request)
        self.assertEqual(payload['period'], '2025-05')
        self.assertEqual(payload['period_display'], 'May 2025')

        with patch(
            'reports.sales_person_report.resolve_sales_person_period',
            return_value=(None, None, 'foo-bar'),
        ):
            weird = SalesPersonReportService.build(self.factory.get('/'))
        self.assertEqual(weird['period'], 'foo-bar')
        self.assertEqual(weird['period_display'], 'foo-bar')
