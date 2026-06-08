"""DailyNoteService queryset and date helpers."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from daily_notes.models import DailyNote
from daily_notes.services import DailyNoteService


class DailyNoteServiceTests(TestCase):
    def setUp(self):
        self.service = DailyNoteService()
        self.alice = User.objects.create_user('alice', password='x')
        self.bob = User.objects.create_user('bob', password='x')
        self.today = date.today()
        self.yesterday = self.today - timedelta(days=1)
        DailyNote.objects.create(
            note_date=self.today,
            title='Alice today',
            content='Shift handover',
            author=self.alice,
        )
        DailyNote.objects.create(
            note_date=self.yesterday,
            title='Bob yesterday',
            content='Stock count',
            author=self.bob,
        )

    def test_build_queryset_scoped_to_author(self):
        qs = self.service.build_queryset(user=self.alice, view_all=False)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().author_id, self.alice.id)

    def test_build_queryset_view_all_returns_everyone(self):
        qs = self.service.build_queryset(user=self.alice, view_all=True)
        self.assertEqual(qs.count(), 2)

    def test_build_queryset_filters_note_date(self):
        qs = self.service.build_queryset(
            user=self.alice,
            view_all=True,
            filters={'note_date': str(self.yesterday)},
        )
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().author_id, self.bob.id)

    def test_build_queryset_author_filter_only_when_view_all(self):
        qs = self.service.build_queryset(
            user=self.alice,
            view_all=False,
            filters={'author': self.bob.id},
        )
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().author_id, self.alice.id)

    def test_build_queryset_author_filter_when_view_all(self):
        qs = self.service.build_queryset(
            user=self.alice,
            view_all=True,
            filters={'author': self.bob.id},
        )
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().author_id, self.bob.id)

    def test_build_queryset_search(self):
        qs = self.service.build_queryset(
            user=self.alice,
            view_all=True,
            filters={'search': 'handover'},
        )
        self.assertEqual(qs.count(), 1)

    def test_recent_dates_scoped_and_sorted(self):
        dates = self.service.recent_dates(user=self.alice, view_all=False)
        self.assertEqual(dates, [self.today])

    def test_recent_dates_view_all(self):
        dates = self.service.recent_dates(user=self.alice, view_all=True)
        self.assertEqual(len(dates), 2)
        self.assertEqual(dates[0], self.today)
