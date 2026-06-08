"""Queryset and recent-dates edge cases."""

from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework import status

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES, sync_default_roles
from daily_notes.models import DailyNote
from daily_notes.tests.test_views import _seed_daily_notes_module
from settings.models import ModuleSetting, ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class DailyNotesQuerysetTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()

    def test_list_filtered_by_note_date(self):
        DailyNote.objects.create(
            note_date=date.today(),
            content='Today',
            author=self.manager_user,
        )
        other = date.today().replace(year=date.today().year - 1)
        DailyNote.objects.create(
            note_date=other,
            content='Old',
            author=self.manager_user,
        )
        response = self.client.get(
            '/api/daily-notes/notes/',
            {'note_date': str(date.today())},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', response.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['content'], 'Today')


class DailyNotesRecentDatesDeniedTests(SalesAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()
        ModuleSetting.objects.filter(
            module='daily_notes',
            key='allow_sales_access',
        ).update(value=False)
        cache.clear()

    def test_recent_dates_denied_when_sales_access_off(self):
        response = self.client.get('/api/daily-notes/notes/recent-dates/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DailyNotesAccessQuerysetTests(SalesAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()

    def test_retrieve_returns_empty_when_note_not_owned(self):
        other = User.objects.create_user('other', password='x')
        UserProfile.objects.create(
            user=other,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
        )
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Private',
            author=other,
        )
        response = self.client.get(f'/api/daily-notes/notes/{note.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
