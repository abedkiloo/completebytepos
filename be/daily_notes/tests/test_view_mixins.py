"""Direct tests for shared view mixin branches."""

from datetime import date

from django.contrib.auth.models import User
from django.test import RequestFactory
from rest_framework import status

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ensure_permissions, sync_default_roles
from daily_notes.models import DailyNote
from daily_notes.tests.test_views import _seed_daily_notes_module
from daily_notes.views import DailyNoteViewSet
from settings.models import ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase


class DailyViewMixinTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles()
        _seed_daily_notes_module()
        self.factory = RequestFactory()
        self.note = DailyNote.objects.create(
            note_date=date.today(),
            content='Mine',
            author=self.manager_user,
        )

    def test_parse_filters_includes_status(self):
        view = DailyNoteViewSet()
        request = self.factory.get(
            '/api/daily-notes/notes/',
            {'note_date': '2026-06-01', 'author': '1', 'search': 'x', 'status': 'open'},
        )
        request.user = self.manager_user
        view.request = request
        filters = view._parse_filters()
        self.assertEqual(filters['note_date'], '2026-06-01')
        self.assertEqual(filters['status'], 'open')

    def test_destroy_other_users_note_forbidden(self):
        other = User.objects.create_user('other_m', password='x')
        UserProfile.objects.create(
            user=other,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
        )
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Theirs',
            author=other,
        )
        response = self.client.delete(f'/api/daily-notes/notes/{note.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_queryset_empty_when_module_disabled(self):
        ModuleSettings.objects.update_or_create(
            module_name='daily_notes',
            defaults={'is_enabled': False},
        )
        view = DailyNoteViewSet()
        request = self.factory.get('/api/daily-notes/notes/')
        request.user = self.manager_user
        view.request = request
        self.assertEqual(view.get_queryset().count(), 0)
