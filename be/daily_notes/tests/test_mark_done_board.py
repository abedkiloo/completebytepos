"""Mark done moves notes to Past and keeps them visible on today's board."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from rest_framework import status

from daily_notes.models import DailyNote
from daily_notes.services import DailyNoteService
from daily_notes.tests.test_views import _seed_daily_notes_module
from utils.tests.api_test_base import ManagerAPITestCase


class MarkDoneBoardTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_daily_notes_module()
        self.today = timezone.localdate()
        self.service = DailyNoteService()

    def test_toggle_done_from_doing_persists_past_column(self):
        """Corrected: Mark done clears in_progress in the DB, not only in memory."""
        note = DailyNote.objects.create(
            note_date=self.today,
            content='Count till',
            author=self.manager_user,
            assigned_to=self.manager_user,
            in_progress=True,
        )
        response = self.client.post(f'/api/daily-notes/notes/{note.id}/toggle-done/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data['is_done'])
        self.assertEqual(response.data['board_column'], 'past')
        self.assertFalse(response.data['in_progress'])
        note.refresh_from_db()
        self.assertTrue(note.is_done)
        self.assertFalse(note.in_progress)
        self.assertEqual(note.board_column, 'past')

    def test_carried_over_done_stays_on_today_past(self):
        """Finishing a carried-over note keeps it on today's list under Past."""
        origin = self.today - timedelta(days=3)
        note = DailyNote.objects.create(
            note_date=origin,
            content='Old open note',
            author=self.manager_user,
            assigned_to=self.manager_user,
            in_progress=True,
        )
        before = self.service.build_queryset(
            user=self.manager_user,
            view_all=True,
            filters={'note_date': str(self.today)},
        )
        self.assertIn(note.id, {n.id for n in before})

        tick = self.client.post(f'/api/daily-notes/notes/{note.id}/toggle-done/')
        self.assertEqual(tick.status_code, status.HTTP_200_OK, tick.data)
        self.assertEqual(tick.data['board_column'], 'past')

        after = self.service.build_queryset(
            user=self.manager_user,
            view_all=True,
            filters={'note_date': str(self.today)},
        )
        self.assertIn(note.id, {n.id for n in after})
        done_today = self.service.build_queryset(
            user=self.manager_user,
            view_all=True,
            filters={'note_date': str(self.today), 'status': 'done'},
        )
        self.assertIn(note.id, {n.id for n in done_today})

    def test_older_done_notes_still_hidden_from_today(self):
        """Regression: notes completed on an earlier day do not reappear today."""
        origin = self.today - timedelta(days=5)
        DailyNote.objects.create(
            note_date=origin,
            content='Finished long ago',
            author=self.manager_user,
            is_done=True,
            completed_at=timezone.now() - timedelta(days=5),
        )
        today_qs = self.service.build_queryset(
            user=self.manager_user,
            view_all=True,
            filters={'note_date': str(self.today)},
        )
        self.assertEqual(today_qs.count(), 0)

    def test_toggle_done_stress_and_untick_returns_to_todo(self):
        note = DailyNote.objects.create(
            note_date=self.today,
            content='Flip often',
            author=self.manager_user,
            assigned_to=self.manager_user,
            in_progress=True,
        )
        for _ in range(12):
            response = self.client.post(
                f'/api/daily-notes/notes/{note.id}/toggle-done/'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        note.refresh_from_db()
        # 12 toggles from done=False → ends done=False, in_progress cleared on last open.
        self.assertFalse(note.is_done)
        self.assertFalse(note.in_progress)
        self.assertEqual(note.board_column, 'todo')


class MarkDoneAssigneeMoveTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_daily_notes_module()
        self.today = timezone.localdate()
        from django.contrib.auth.models import User

        from accounts.models import Role, UserProfile
        from accounts.role_definitions import ROLE_SALES, sync_default_roles

        sync_default_roles()
        self.assignee = User.objects.create_user('board_assignee', password='pass12345')
        UserProfile.objects.create(
            user=self.assignee,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        self.outsider = User.objects.create_user('board_outsider', password='pass12345')
        UserProfile.objects.create(
            user=self.outsider,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )

    def test_assignee_can_move_board_column_only(self):
        """Security: assignee may move columns; full edits stay forbidden."""
        note = DailyNote.objects.create(
            note_date=self.today,
            content='Assigned note',
            author=self.manager_user,
            assigned_to=self.assignee,
        )
        self.client.force_authenticate(self.assignee)
        move = self.client.patch(
            f'/api/daily-notes/notes/{note.id}/',
            {'board_column': 'past'},
            format='json',
        )
        self.assertEqual(move.status_code, status.HTTP_200_OK, move.data)
        self.assertEqual(move.data['board_column'], 'past')
        note.refresh_from_db()
        self.assertTrue(note.is_done)

        edit = self.client.patch(
            f'/api/daily-notes/notes/{note.id}/',
            {'content': 'Hijacked', 'board_column': 'todo'},
            format='json',
        )
        self.assertEqual(edit.status_code, status.HTTP_403_FORBIDDEN)
        note.refresh_from_db()
        self.assertEqual(note.content, 'Assigned note')
        self.assertTrue(note.is_done)

    def test_outsider_cannot_toggle_or_move(self):
        """IDOR: another sales user cannot mark someone else's note done."""
        note = DailyNote.objects.create(
            note_date=self.today,
            content='Private',
            author=self.manager_user,
            assigned_to=self.assignee,
        )
        self.client.force_authenticate(self.outsider)
        tick = self.client.post(f'/api/daily-notes/notes/{note.id}/toggle-done/')
        self.assertIn(
            tick.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )
        move = self.client.patch(
            f'/api/daily-notes/notes/{note.id}/',
            {'board_column': 'past'},
            format='json',
        )
        self.assertIn(
            move.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )
        note.refresh_from_db()
        self.assertFalse(note.is_done)
