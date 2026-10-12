"""Unit tests for Monday–Sunday calendar-week dashboard summary."""

from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from reports.week_summary import (
    coerce_day_key,
    monday_of_week,
    week_bounds,
    week_sales_summary,
)
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


class MondayWeekBoundsTests(TestCase):
    def test_monday_of_week_is_always_monday(self):
        for offset in range(7):
            day = timezone.localdate() - timedelta(days=offset)
            monday = monday_of_week(day)
            self.assertEqual(monday.weekday(), 0)
            self.assertLessEqual(monday, day)
            self.assertLessEqual(day, monday + timedelta(days=6))

    def test_week_bounds_span_seven_days(self):
        monday, sunday = week_bounds(timezone.localdate())
        self.assertEqual(monday.weekday(), 0)
        self.assertEqual(sunday.weekday(), 6)
        self.assertEqual((sunday - monday).days, 6)


class WeekSalesSummaryTests(TestCase):
    def test_empty_week(self):
        data = week_sales_summary(Sale.objects.filter(status='completed'))
        self.assertEqual(data['sales_count'], 0)
        self.assertEqual(data['total'], 0.0)
        self.assertEqual(len(data['days']), 7)
        self.assertEqual(data['days'][0]['label'], 'Mon')
        self.assertEqual(data['days'][-1]['label'], 'Sun')
        self.assertTrue(all(day['sales_count'] == 0 for day in data['days']))

    def test_groups_by_day_and_ignores_prior_week_sales(self):
        user = User.objects.create_user(username='week_sum', password='x')
        today = timezone.localdate()
        monday = monday_of_week(today)
        in_week = timezone.make_aware(datetime.combine(monday, datetime.min.time())) + timedelta(
            hours=10
        )
        prior_week = timezone.make_aware(
            datetime.combine(monday - timedelta(days=1), datetime.min.time())
        ) + timedelta(hours=10)
        Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('20'),
            total=Decimal('20'),
            amount_paid=Decimal('20'),
            cashier=user,
            occurred_at=in_week,
        )
        Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('99'),
            total=Decimal('99'),
            amount_paid=Decimal('99'),
            cashier=user,
            occurred_at=prior_week,
        )
        data = week_sales_summary(Sale.objects.filter(status='completed'))
        self.assertEqual(data['sales_count'], 1)
        self.assertEqual(data['total'], 20.0)
        self.assertEqual(data['week_start'], monday.isoformat())
        self.assertEqual(sum(day['total'] for day in data['days']), 20.0)
        self.assertEqual(data['days'][0]['date'], monday.isoformat())
        self.assertTrue(any(day['sales_count'] == 1 for day in data['days']))
