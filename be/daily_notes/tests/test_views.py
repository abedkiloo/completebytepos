"""Daily notes API access rules."""

from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, ensure_permissions, sync_default_roles
from daily_notes.models import DailyNote
from settings.models import ModuleSetting, ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


def _seed_daily_notes_module():
    cache.clear()
    ModuleSettings.objects.update_or_create(
        module_name='daily_notes',
        defaults={'is_enabled': True},
    )
    for key, default in (
        ('allow_sales_access', True),
        ('allow_manager_view_all', True),
        ('allow_sales_view_all', False),
    ):
        ModuleSetting.objects.update_or_create(
            module='daily_notes',
            key=key,
            defaults={
                'label': key,
                'description': '',
                'default_value': default,
                'value': default,
            },
        )


class DailyNotesAccessTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()
        self.sales_user = User.objects.create_user('sales2', password='sales123')
        UserProfile.objects.create(
            user=self.sales_user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
        )
        self.sales_note = DailyNote.objects.create(
            note_date=date.today(),
            title='Sales shift',
            content='Opened on time',
            author=self.sales_user,
        )
        self.manager_note = DailyNote.objects.create(
            note_date=date.today(),
            title='Manager review',
            content='Stock check done',
            author=self.manager_user,
        )

    def test_manager_lists_all_notes(self):
        response = self.client.get('/api/daily-notes/notes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row['id'] for row in response.data.get('results', response.data)}
        self.assertIn(self.sales_note.id, ids)
        self.assertIn(self.manager_note.id, ids)

    def test_manager_creates_note(self):
        response = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'title': 'Closing',
                'content': 'Counted drawer',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_manager_retrieves_and_updates_own_note(self):
        response = self.client.get(f'/api/daily-notes/notes/{self.manager_note.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.patch(
            f'/api/daily-notes/notes/{self.manager_note.id}/',
            {'content': 'Updated review'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.manager_note.refresh_from_db()
        self.assertEqual(self.manager_note.content, 'Updated review')

    def test_manager_cannot_edit_other_users_note(self):
        response = self.client.patch(
            f'/api/daily-notes/notes/{self.sales_note.id}/',
            {'content': 'Nope'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_delete_other_users_note(self):
        response = self.client.delete(f'/api/daily-notes/notes/{self.sales_note.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_deletes_own_note(self):
        note_id = self.manager_note.id
        response = self.client.delete(f'/api/daily-notes/notes/{note_id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DailyNote.objects.filter(id=note_id).exists())

    def test_recent_dates_lists_distinct_days(self):
        response = self.client.get('/api/daily-notes/notes/recent-dates/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(date.today(), response.data['dates'])

    def test_list_filters_by_search_and_author(self):
        response = self.client.get(
            '/api/daily-notes/notes/',
            {'search': 'Sales shift', 'author': self.sales_user.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', response.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], self.sales_note.id)


class DailyNotesSalesTests(SalesAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()
        self.other = User.objects.create_user('mgr2', password='mgr123')
        UserProfile.objects.create(
            user=self.other,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
        )
        self.own = DailyNote.objects.create(
            note_date=date.today(),
            content='My note',
            author=self.sales_user,
        )
        self.other_note = DailyNote.objects.create(
            note_date=date.today(),
            content='Manager only',
            author=self.other,
        )

    def test_sales_sees_only_own_notes(self):
        response = self.client.get('/api/daily-notes/notes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', response.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], self.own.id)

    def test_sales_cannot_edit_other_note(self):
        response = self.client.patch(
            f'/api/daily-notes/notes/{self.other_note.id}/',
            {'content': 'Hacked'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_sales_creates_updates_and_deletes_own_note(self):
        create = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'title': 'Closing',
                'content': 'End of day',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        note_id = create.data['id']
        patch = self.client.patch(
            f'/api/daily-notes/notes/{note_id}/',
            {'content': 'End of day — updated'},
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        delete = self.client.delete(f'/api/daily-notes/notes/{note_id}/')
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)

    def test_sales_recent_dates_own_only(self):
        response = self.client.get('/api/daily-notes/notes/recent-dates/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['dates']), 1)

    def test_sales_denied_when_module_sales_access_off(self):
        ModuleSetting.objects.filter(
            module='daily_notes',
            key='allow_sales_access',
        ).update(value=False)
        cache.clear()
        response = self.client.get('/api/daily-notes/notes/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DailyNotesModuleDisabledTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        ModuleSettings.objects.update_or_create(
            module_name='daily_notes',
            defaults={'is_enabled': False},
        )

    def test_disabled_module_returns_forbidden(self):
        DailyNote.objects.create(
            note_date=date.today(),
            content='Hidden',
            author=self.manager_user,
        )
        response = self.client.get('/api/daily-notes/notes/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DailyNotesSalesDeskWithoutNotesPermTests(SalesAPITestCase):
    """UAT sales roles often have sales.view but not daily_notes.view."""

    def setUp(self):
        super().setUp()
        ensure_permissions()
        _seed_daily_notes_module()
        role = Role.objects.create(name='UAT Sales Person', is_active=True)
        role.permissions.add(
            Permission.objects.get(module='sales', action='view'),
            Permission.objects.get(module='pos', action='view'),
        )
        self.desk_user = User.objects.create_user('uat_sales_desk', password='x')
        UserProfile.objects.create(
            user=self.desk_user,
            role='cashier',
            custom_role=role,
            is_active=True,
        )
        self.assertFalse(self.desk_user.profile.has_permission('daily_notes', 'view'))
        token = RefreshToken.for_user(self.desk_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_sales_desk_lists_notes_without_daily_notes_view(self):
        own = DailyNote.objects.create(
            note_date=date.today(),
            content='Till opened',
            author=self.desk_user,
        )
        assigned = DailyNote.objects.create(
            note_date=date.today(),
            title='Approval rejected: sale completion',
            content='Wrong prices\nsale_id: 9',
            author=self.sales_user,
            assigned_to=self.desk_user,
            is_sticky=True,
        )
        response = self.client.get('/api/daily-notes/notes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row['id'] for row in response.data.get('results', response.data)}
        self.assertIn(own.id, ids)
        self.assertIn(assigned.id, ids)

    def test_sales_desk_creates_note_without_daily_notes_create(self):
        response = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'title': 'Shift',
                'content': 'Counted drawer',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_sales_desk_lists_tasks(self):
        response = self.client.get('/api/daily-notes/tasks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
