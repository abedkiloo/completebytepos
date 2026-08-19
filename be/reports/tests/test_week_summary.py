"""Unit tests for last-7-days dashboard summary."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from reports.week_summary import coerce_day_key, week_sales_summary
from sales.models import Sale


class CoerceDayKeyTests(TestCase):
    def test_none(self):
        self.assertIsNone(coerce_day_key(None))

    def test_date_passthrough(self):
        day = timezone.now().date()
        self.assertEqual(coerce_day_key(day), day)

    def test_datetime_to_date(self):
        when = timezone.now()
        self.assertEqual(coerce_day_key(when), when.date())


class WeekSalesSummaryTests(TestCase):
    def test_empty_week(self):
        data = week_sales_summary(Sale.objects.filter(status='completed'))
        self.assertEqual(data['sales_count'], 0)
        self.assertEqual(data['total'], 0.0)
        self.assertEqual(len(data['days']), 7)
        self.assertTrue(all(day['sales_count'] == 0 for day in data['days']))

    def test_groups_by_day_and_ignores_older_sales(self):
        user = User.objects.create_user(username='week_sum', password='x')
        Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('20'),
            total=Decimal('20'),
            amount_paid=Decimal('20'),
            cashier=user,
            occurred_at=timezone.now() - timedelta(days=2),
        )
        Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('99'),
            total=Decimal('99'),
            amount_paid=Decimal('99'),
            cashier=user,
            occurred_at=timezone.now() - timedelta(days=10),
        )
        data = week_sales_summary(Sale.objects.filter(status='completed'))
        self.assertEqual(data['sales_count'], 1)
        self.assertEqual(data['total'], 20.0)
        self.assertEqual(sum(day['total'] for day in data['days']), 20.0)
        self.assertTrue(any(day['sales_count'] == 1 for day in data['days']))
