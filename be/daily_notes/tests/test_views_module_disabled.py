"""Module disabled queryset branches."""

from datetime import date

from django.contrib.auth.models import User

from accounts.models import UserProfile
from accounts.role_definitions import sync_default_roles
from daily_notes.models import DailyNote
from daily_notes.views import DailyNoteViewSet
from settings.models import ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase


class DailyNotesViewSetQuerysetTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        ModuleSettings.objects.update_or_create(
            module_name='daily_notes',
            defaults={'is_enabled': False},
        )

    def test_get_queryset_empty_when_module_disabled(self):
        DailyNote.objects.create(
            note_date=date.today(),
            content='Hidden',
            author=self.manager_user,
        )
        view = DailyNoteViewSet()
        view.request = type('R', (), {'user': self.manager_user, 'query_params': {}})()
        self.assertEqual(view.get_queryset().count(), 0)

    def test_get_queryset_empty_when_user_lacks_access(self):
        ModuleSettings.objects.update_or_create(
            module_name='daily_notes',
            defaults={'is_enabled': True},
        )
        orphan = User.objects.create_user('no_role', password='x')
        UserProfile.objects.create(user=orphan, role='cashier', custom_role=None)
        view = DailyNoteViewSet()
        view.request = type('R', (), {'user': orphan, 'query_params': {}})()
        self.assertEqual(view.get_queryset().count(), 0)
