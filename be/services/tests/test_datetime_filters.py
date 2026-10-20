"""Tests for inclusive date/datetime filter bounds."""

from datetime import datetime, time
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from services.datetime_filters import inclusive_end_datetime, inclusive_start_datetime


class InclusiveDatetimeFilterTests(TestCase):
    def test_none_and_empty_return_none(self):
        self.assertIsNone(inclusive_start_datetime(None))
        self.assertIsNone(inclusive_start_datetime(''))
        self.assertIsNone(inclusive_end_datetime(None))
        self.assertIsNone(inclusive_end_datetime(''))

    def test_date_only_strings_expand_to_day_bounds(self):
        start = inclusive_start_datetime('2024-06-15')
        end = inclusive_end_datetime('2024-06-15')
        self.assertTrue(timezone.is_aware(start))
        self.assertTrue(timezone.is_aware(end))
        self.assertEqual(start.time(), time.min)
        self.assertEqual(end.time(), time.max)

    def test_datetime_string_naive_becomes_aware(self):
        start = inclusive_start_datetime('2024-06-15T10:30:00')
        end = inclusive_end_datetime('2024-06-15T10:30:00')
        self.assertTrue(timezone.is_aware(start))
        self.assertTrue(timezone.is_aware(end))

    def test_datetime_string_already_aware_unchanged(self):
        tz = timezone.get_current_timezone()
        aware = timezone.make_aware(datetime(2024, 6, 15, 10, 30, 0), tz)
        iso = aware.isoformat()
        self.assertEqual(inclusive_start_datetime(iso), aware)
        self.assertEqual(inclusive_end_datetime(iso), aware)

    def test_unparseable_value_passthrough(self):
        raw = 'not-a-date'
        self.assertEqual(inclusive_start_datetime(raw), raw)
        self.assertEqual(inclusive_end_datetime(raw), raw)

    @patch('services.datetime_filters.timezone.is_naive', return_value=False)
    def test_date_only_when_start_already_aware(self, _is_naive):
        start = inclusive_start_datetime('2024-06-15')
        self.assertEqual(start.time(), time.min)

    @patch('services.datetime_filters.timezone.is_naive', return_value=False)
    def test_date_only_when_end_already_aware(self, _is_naive):
        end = inclusive_end_datetime('2024-06-15')
        self.assertEqual(end.time(), time.max)
