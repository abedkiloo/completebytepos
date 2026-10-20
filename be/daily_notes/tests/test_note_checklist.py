"""Daily note optional checklist — notes required, checklist optional."""

from django.utils import timezone
from rest_framework import status

from daily_notes.models import DailyNote, DailyNoteChecklistItem
from utils.tests.api_test_base import ManagerAPITestCase


class DailyNoteChecklistTests(ManagerAPITestCase):
    def test_create_note_with_optional_checklist(self):
        today = timezone.localdate().isoformat()
        response = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': today,
                'content': 'Closing handover',
                'checklist_items': [
                    {'label': 'Count till', 'is_done': False},
                    {'label': 'Lock store', 'is_done': True},
                ],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['content'], 'Closing handover')
        items = response.data.get('checklist_items') or []
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['label'], 'Count till')
        self.assertFalse(items[0]['is_done'])
        self.assertEqual(items[1]['label'], 'Lock store')
        self.assertTrue(items[1]['is_done'])
        note = DailyNote.objects.get(pk=response.data['id'])
        self.assertEqual(note.checklist_items.count(), 2)

    def test_create_note_without_checklist_ok(self):
        today = timezone.localdate().isoformat()
        response = self.client.post(
            '/api/daily-notes/notes/',
            {'note_date': today, 'content': 'Plain note only'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data.get('checklist_items') or [], [])

    def test_reject_empty_content_even_with_checklist(self):
        today = timezone.localdate().isoformat()
        response = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': today,
                'content': '   ',
                'checklist_items': [{'label': 'Only checklist'}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_toggle_checklist_item(self):
        note = DailyNote.objects.create(
            note_date=timezone.localdate(),
            content='Shift note',
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        item = DailyNoteChecklistItem.objects.create(
            daily_note=note,
            label='Sweep floor',
            sort_order=0,
        )
        response = self.client.post(
            f'/api/daily-notes/notes/{note.id}/checklist-items/{item.id}/toggle-done/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data['is_done'])
        item.refresh_from_db()
        self.assertTrue(item.is_done)
        self.assertIsNotNone(item.completed_at)

    def test_person_filter_matches_author_or_assignee(self):
        from django.contrib.auth.models import User

        from accounts.models import Role, UserProfile
        from accounts.role_definitions import ROLE_SUPER_ADMIN, ensure_permissions, sync_default_roles
        from rest_framework_simplejwt.tokens import RefreshToken

        ensure_permissions()
        sync_default_roles()
        other = User.objects.create_user('dn_other', password='x')
        UserProfile.objects.create(
            user=other,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        today = timezone.localdate()
        DailyNote.objects.create(
            note_date=today,
            content='Mine',
            author=self.manager_user,
            assigned_to=None,
        )
        DailyNote.objects.create(
            note_date=today,
            content='For other',
            author=self.manager_user,
            assigned_to=other,
        )
        admin = User.objects.create_user('dn_admin', password='x', is_staff=True)
        UserProfile.objects.create(
            user=admin,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(admin).access_token}')
        response = client.get(
            '/api/daily-notes/notes/',
            {'note_date': today.isoformat(), 'person': other.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        rows = response.data.get('results') or response.data
        contents = {row['content'] for row in rows}
        self.assertIn('For other', contents)
        self.assertNotIn('Mine', contents)
