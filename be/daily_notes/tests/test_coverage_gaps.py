"""Fill remaining daily_notes gate coverage gaps."""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES, sync_default_roles
from daily_notes.models import DailyNote, DailyNoteChecklistItem, DailyTask
from daily_notes.serializers import DailyTaskSerializer, replace_note_checklist
from daily_notes.services import (
    DailyTaskService,
    carried_over_days,
    create_notes_for_assignees,
    parse_filter_date,
)
from daily_notes.tests.test_views import _seed_daily_notes_module
from daily_notes.views import DailyNoteViewSet, DailyTaskViewSet
from settings.models import ModuleSetting, ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase


class DailyNotesServiceGapTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()
        self.today = date.today()

    def test_parse_filter_date_invalid_and_carried_over_bad_origin(self):
        self.assertIsNone(parse_filter_date('not-a-date'))
        self.assertIsNone(parse_filter_date('2025-13-40'))
        self.assertEqual(
            carried_over_days(origin='garbage', as_of=self.today),
            0,
        )
        self.assertEqual(parse_filter_date(self.today), self.today)

    def test_create_notes_truncates_huge_staff_fanout(self):
        fake_users = [User(id=i, username=f'u{i}') for i in range(1, 505)]
        with patch('daily_notes.services.active_staff_users', return_value=fake_users):
            with patch.object(DailyNote.objects, 'bulk_create', side_effect=lambda rows, **kw: rows):
                notes = create_notes_for_assignees(
                    author=self.manager_user,
                    note_date=self.today,
                    content='Broadcast',
                    assign_to_all=True,
                )
        self.assertEqual(len(notes), 500)

    def test_task_person_filter_and_invalid_day_raw(self):
        from django.core.exceptions import ValidationError

        alice = User.objects.create_user('gap_alice', password='x')
        DailyTask.objects.create(
            task_date=self.today,
            title='Alice task',
            author=self.manager_user,
            assigned_to=alice,
        )
        DailyTask.objects.create(
            task_date=self.today,
            title='Other task',
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        # Invalid day_raw hits the else branch then Django date prep raises.
        with self.assertRaises(ValidationError):
            DailyTaskService().build_queryset(
                user=self.manager_user,
                view_all=True,
                filters={'person': alice.id, 'task_date': 'not-iso'},
            )
        person_only = DailyTaskService().build_queryset(
            user=self.manager_user,
            view_all=True,
            filters={'person': alice.id},
        )
        self.assertEqual(person_only.count(), 1)
        self.assertEqual(person_only.first().assigned_to_id, alice.id)

    def test_pending_count_for_user(self):
        DailyTask.objects.create(
            task_date=self.today,
            title='Open',
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        DailyTask.objects.create(
            task_date=self.today,
            title='Done',
            is_done=True,
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        self.assertEqual(
            DailyTaskService().pending_count_for_user(user=self.manager_user),
            1,
        )


class DailyNotesSerializerGapTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()

    def test_replace_checklist_accepts_model_instances_and_skips_blank(self):
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Has checklist',
            author=self.manager_user,
        )
        existing = DailyNoteChecklistItem(
            label='From model',
            is_done=True,
            sort_order=None,
        )
        replace_note_checklist(note, [existing, {'label': '  ', 'is_done': False}])
        labels = list(note.checklist_items.values_list('label', flat=True))
        self.assertEqual(labels, ['From model'])
        self.assertTrue(note.checklist_items.get().is_done)
        self.assertEqual(str(note.checklist_items.get()), 'From model (done)')
        open_item = DailyNoteChecklistItem.objects.create(
            daily_note=note, label='Still open', sort_order=1
        )
        self.assertEqual(str(open_item), 'Still open (open)')

    def test_create_note_with_board_column_and_done_requires_content(self):
        today = timezone.localdate().isoformat()
        created = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': today,
                'content': 'Board create',
                'board_column': 'doing',
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(created.data['board_column'], 'doing')

        bad = self.client.post(
            '/api/daily-notes/notes/',
            {'note_date': today, 'content': '', 'is_done': True},
            format='json',
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_task_serializer_unassigned_name_and_done_requires_title(self):
        task = DailyTask(
            task_date=date.today(),
            title='Solo',
            author=self.manager_user,
            assigned_to=None,
        )
        data = DailyTaskSerializer(
            task,
            context={'request': type('R', (), {'user': self.manager_user})()},
        ).data
        self.assertEqual(data['assigned_to_name'], '')

        existing = DailyTask.objects.create(
            task_date=date.today(),
            title='Has title',
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        existing.title = ''
        existing.save(update_fields=['title'])
        ser = DailyTaskSerializer(
            existing,
            data={'is_done': True},
            partial=True,
            context={'request': type('R', (), {'user': self.manager_user})()},
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('title', ser.errors)


class DailyNotesViewGapTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()
        self.sales_user = User.objects.create_user('gap_sales', password='sales123')
        UserProfile.objects.create(
            user=self.sales_user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )

    def test_staff_search_and_assigned_to_filter_param(self):
        staff = self.client.get('/api/daily-notes/notes/staff/', {'q': 'phase2'})
        self.assertEqual(staff.status_code, status.HTTP_200_OK)
        self.assertTrue(any(row['username'] == 'phase2_manager' for row in staff.data))

        DailyNote.objects.create(
            note_date=date.today(),
            content='Assigned filter',
            author=self.manager_user,
            assigned_to=self.sales_user,
        )
        filtered = self.client.get(
            '/api/daily-notes/notes/',
            {'assigned_to': self.sales_user.id, 'note_date': str(date.today())},
        )
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        rows = filtered.data.get('results') or filtered.data
        self.assertTrue(any(r['content'] == 'Assigned filter' for r in rows))

    def test_checklist_toggle_forbidden_for_outsider(self):
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Private',
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        item = DailyNoteChecklistItem.objects.create(
            daily_note=note, label='Nope', sort_order=0
        )
        token = RefreshToken.for_user(self.sales_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        # Ensure sales can access module but not this note.
        ModuleSetting.objects.update_or_create(
            module='daily_notes',
            key='allow_sales_view_all',
            defaults={
                'label': 'allow_sales_view_all',
                'description': '',
                'default_value': False,
                'value': False,
            },
        )
        cache.clear()
        res = self.client.post(
            f'/api/daily-notes/notes/{note.id}/checklist-items/{item.id}/toggle-done/'
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_may_toggle_note(self):
        admin = User.objects.create_superuser('gap_admin', 'a@b.co', 'x')
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Admin tick',
            author=self.manager_user,
            assigned_to=self.sales_user,
        )
        view = DailyNoteViewSet()
        view.request = type('R', (), {'user': admin})()
        self.assertTrue(view._may_toggle_note(note))

    def test_task_edit_toggle_permissions_and_pending_count(self):
        other = User.objects.create_user('gap_other', password='x')
        UserProfile.objects.create(
            user=other,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        task = DailyTask.objects.create(
            task_date=date.today(),
            title='Owned by manager',
            author=self.manager_user,
            assigned_to=other,
        )
        # Assignee can see the task but cannot edit/delete (not author / view_all).
        token = RefreshToken.for_user(other)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        ModuleSetting.objects.update_or_create(
            module='daily_notes',
            key='allow_sales_view_all',
            defaults={
                'label': 'allow_sales_view_all',
                'description': '',
                'default_value': False,
                'value': False,
            },
        )
        cache.clear()
        patch = self.client.patch(
            f'/api/daily-notes/tasks/{task.id}/',
            {'title': 'Hacked'},
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_403_FORBIDDEN)
        delete = self.client.delete(f'/api/daily-notes/tasks/{task.id}/')
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)

        # Assignee may toggle; author may toggle; superuser may edit.
        view = DailyTaskViewSet()
        view.request = type('R', (), {'user': other})()
        self.assertTrue(view._may_toggle_task(task))
        view.request = type('R', (), {'user': self.manager_user})()
        self.assertTrue(view._may_toggle_task(task))
        admin = User.objects.create_superuser('gap_su', 's@b.co', 'x')
        view.request = type('R', (), {'user': admin})()
        self.assertTrue(view._may_edit_task(task))
        self.assertTrue(view._may_toggle_task(task))

        # Manager pending-count happy path
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.manager_user).access_token}'
        )
        count = self.client.get('/api/daily-notes/tasks/pending-count/')
        self.assertEqual(count.status_code, status.HTTP_200_OK)
        self.assertIn('count', count.data)

    def test_pending_count_denied_without_access(self):
        ModuleSettings.objects.update_or_create(
            module_name='daily_notes',
            defaults={'is_enabled': True},
        )
        empty_role = Role.objects.create(name='No desk gap', is_active=True)
        orphan = User.objects.create_user('gap_orphan', password='x')
        UserProfile.objects.create(user=orphan, role='cashier', custom_role=empty_role)
        view = DailyTaskViewSet()
        view.request = type('R', (), {'user': orphan})()
        view.format_kwarg = None
        denied = view.pending_count(view.request)
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
