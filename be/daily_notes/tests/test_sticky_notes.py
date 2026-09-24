"""Sticky vs general daily notes, blocking gate, and ticking."""

from datetime import date

from django.contrib.auth.models import User
from rest_framework import status

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES, sync_default_roles
from daily_notes.models import DailyNote
from daily_notes.tests.test_views import _seed_daily_notes_module
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class StickyNoteAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()
        self.sales_user = User.objects.create_user('sticky_sales', password='sales123')
        UserProfile.objects.create(
            user=self.sales_user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
        )

    def test_manager_creates_sticky_note_for_sales(self):
        response = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'title': 'Till check',
                'content': 'Count the drawer before you sell.',
                'is_sticky': True,
                'assigned_to': self.sales_user.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(response.data['is_sticky'])
        self.assertEqual(response.data['assigned_to'], self.sales_user.id)
        self.assertFalse(response.data['is_done'])

        self.client.force_authenticate(self.sales_user)
        blocking = self.client.get('/api/daily-notes/notes/blocking/')
        self.assertEqual(len(blocking.data), 1)
        listed = self.client.get('/api/daily-notes/notes/')
        ids = {row['id'] for row in listed.data.get('results', listed.data)}
        self.assertIn(response.data['id'], ids)

    def test_assigned_general_note_appears_on_login_inbox(self):
        created = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'content': 'Please restock sugar before opening',
                'is_sticky': False,
                'assigned_to': self.sales_user.id,
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.client.force_authenticate(self.sales_user)
        inbox = self.client.get('/api/daily-notes/notes/blocking/')
        self.assertEqual(len(inbox.data), 1)
        self.assertFalse(inbox.data[0]['is_sticky'])
        self.assertEqual(inbox.data[0]['assigned_to'], self.sales_user.id)

    def test_general_note_is_not_blocking(self):
        created = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'content': 'Nice weather at the shop',
                'is_sticky': False,
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertFalse(created.data['is_sticky'])
        blocking = self.client.get('/api/daily-notes/notes/blocking/')
        self.assertEqual(blocking.data, [])

    def test_manager_ticks_and_unticks_general_note(self):
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Follow up supplier',
            author=self.manager_user,
        )
        tick = self.client.post(f'/api/daily-notes/notes/{note.id}/toggle-done/')
        self.assertEqual(tick.status_code, status.HTTP_200_OK)
        self.assertTrue(tick.data['is_done'])
        self.assertIsNotNone(tick.data['completed_at'])
        untick = self.client.post(f'/api/daily-notes/notes/{note.id}/toggle-done/')
        self.assertFalse(untick.data['is_done'])
        self.assertIsNone(untick.data['completed_at'])

    def test_sales_cannot_assign_sticky_to_someone_else(self):
        self.client.force_authenticate(self.sales_user)
        response = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'content': 'Do this now',
                'is_sticky': True,
                'assigned_to': self.manager_user.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sales_sticky_defaults_to_self_and_blocks(self):
        self.client.force_authenticate(self.sales_user)
        response = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'content': 'Finish stock count first',
                'is_sticky': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['assigned_to'], self.sales_user.id)
        blocking = self.client.get('/api/daily-notes/notes/blocking/')
        self.assertEqual(len(blocking.data), 1)

    def test_kind_filter_and_staff_list(self):
        DailyNote.objects.create(
            note_date=date.today(),
            content='Sticky',
            is_sticky=True,
            author=self.manager_user,
            assigned_to=self.sales_user,
        )
        DailyNote.objects.create(
            note_date=date.today(),
            content='General',
            author=self.manager_user,
        )
        sticky = self.client.get('/api/daily-notes/notes/', {'kind': 'sticky'})
        general = self.client.get('/api/daily-notes/notes/', {'kind': 'general'})
        sticky_rows = sticky.data.get('results', sticky.data)
        general_rows = general.data.get('results', general.data)
        self.assertTrue(all(row['is_sticky'] for row in sticky_rows))
        self.assertTrue(all(not row['is_sticky'] for row in general_rows))
        staff = self.client.get('/api/daily-notes/notes/staff/')
        self.assertEqual(staff.status_code, status.HTTP_200_OK)
        ids = {row['id'] for row in staff.data}
        self.assertIn(self.sales_user.id, ids)

    def test_str_and_toggle_forbidden_for_bystander(self):
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Secret',
            is_sticky=True,
            author=self.manager_user,
            assigned_to=self.sales_user,
        )
        self.assertIn('must-tick', str(note))
        other = User.objects.create_user('bystander', password='x')
        UserProfile.objects.create(
            user=other,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
        )
        self.client.force_authenticate(other)
        res = self.client.post(f'/api/daily-notes/notes/{note.id}/toggle-done/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        missing = self.client.post('/api/daily-notes/notes/999999/toggle-done/')
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(self.sales_user)
        allowed = self.client.post(f'/api/daily-notes/notes/{note.id}/toggle-done/')
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

    def test_update_sticky_and_tick_via_put(self):
        create = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'content': 'Need a count',
                'is_sticky': True,
                'assigned_to': self.sales_user.id,
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        note_id = create.data['id']
        patch = self.client.patch(
            f'/api/daily-notes/notes/{note_id}/',
            {'is_done': True, 'content': 'Need a count'},
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK, patch.data)
        self.assertTrue(patch.data['is_done'])
        reopen = self.client.patch(
            f'/api/daily-notes/notes/{note_id}/',
            {'is_sticky': False, 'is_done': False},
            format='json',
        )
        self.assertEqual(reopen.status_code, status.HTTP_200_OK, reopen.data)
        self.assertFalse(reopen.data['is_sticky'])
        doing = self.client.patch(
            f'/api/daily-notes/notes/{note_id}/',
            {'board_column': 'doing', 'content': 'Need a count'},
            format='json',
        )
        self.assertEqual(doing.status_code, status.HTTP_200_OK, doing.data)
        self.assertEqual(doing.data['board_column'], 'doing')
        self.assertTrue(doing.data['in_progress'])
        past = self.client.patch(
            f'/api/daily-notes/notes/{note_id}/',
            {'board_column': 'past', 'content': 'Need a count'},
            format='json',
        )
        self.assertEqual(past.status_code, status.HTTP_200_OK, past.data)
        self.assertEqual(past.data['board_column'], 'past')
        filtered = self.client.get('/api/daily-notes/notes/', {'is_sticky': 'true'})
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        open_notes = self.client.get('/api/daily-notes/notes/', {'status': 'open'})
        self.assertEqual(open_notes.status_code, status.HTTP_200_OK)


class StickyNoteSalesStaffTests(SalesAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()

    def test_sales_staff_list_forbidden(self):
        response = self.client.get('/api/daily-notes/notes/staff/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
