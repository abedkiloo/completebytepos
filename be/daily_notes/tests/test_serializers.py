from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from daily_notes.models import DailyNote
from daily_notes.serializers import DailyNoteSerializer, _author_display


class DailyNoteSerializerTests(TestCase):
    def test_author_name_uses_full_name_or_username(self):
        user = User.objects.create_user('jdoe', password='x', first_name='Jane', last_name='Doe')
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Test',
            author=user,
        )
        data = DailyNoteSerializer(note).data
        self.assertEqual(data['author_name'], 'Jane Doe')
        self.assertEqual(data['author_username'], 'jdoe')

    def test_author_name_falls_back_to_username(self):
        user = User.objects.create_user('plainuser', password='x')
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Test',
            author=user,
        )
        self.assertEqual(DailyNoteSerializer(note).data['author_name'], 'plainuser')

    def test_sticky_fields_and_tick(self):
        user = User.objects.create_user('stickyu', password='x', first_name='Sam')
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Block POS',
            is_sticky=True,
            author=user,
            assigned_to=user,
        )
        data = DailyNoteSerializer(note).data
        self.assertTrue(data['is_sticky'])
        self.assertFalse(data['is_done'])
        self.assertEqual(data['assigned_to_name'], 'Sam')
        note.mark_done(done=True)
        self.assertTrue(note.is_done)
        self.assertIsNotNone(note.completed_at)
        note.mark_done(done=False)
        self.assertFalse(note.is_done)
        self.assertIsNone(note.completed_at)
        self.assertIn('must-tick', str(note))

    def test_general_note_str(self):
        user = User.objects.create_user('genu', password='x')
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Just a log',
            author=user,
        )
        self.assertIn('note', str(note))
        data = DailyNoteSerializer(note).data
        self.assertEqual(data['assigned_to_username'], '')
        self.assertEqual(data['assigned_role_name'], '')
        self.assertNotIn('created_count', data)
        self.assertEqual(_author_display(None), '')
        ser = DailyNoteSerializer()
        note.mark_done(done=True)
        ser._apply_completion(note, True)
        self.assertTrue(note.is_done)
        ser._apply_completion(note, False)
        self.assertFalse(note.is_done)

    def test_board_column_todo_doing_past(self):
        user = User.objects.create_user('boardu', password='x')
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Move me',
            author=user,
        )
        ser = DailyNoteSerializer(note)
        self.assertEqual(ser.data['board_column'], 'todo')
        note.move_to_board('doing')
        self.assertEqual(note.board_column, 'doing')
        self.assertTrue(note.in_progress)
        self.assertFalse(note.is_done)
        note.move_to_board('past')
        self.assertEqual(note.board_column, 'past')
        self.assertTrue(note.is_done)
        self.assertFalse(note.in_progress)
        note.move_to_board('todo')
        self.assertEqual(note.board_column, 'todo')
        self.assertFalse(note.is_done)
        self.assertFalse(note.in_progress)

    def test_cannot_tick_empty_note_and_can_reassign(self):
        user = User.objects.create_user('emptytick', password='x')
        other = User.objects.create_user('other_n', password='x')
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Has text',
            author=user,
            assigned_to=user,
        )
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.patch('/api/daily-notes/notes/1/')
        request.user = user
        ser = DailyNoteSerializer(
            note,
            data={'is_done': True, 'content': ''},
            partial=True,
            context={'request': request},
        )
        self.assertFalse(ser.is_valid())
        ok = DailyNoteSerializer(
            note,
            data={'assigned_to': other.id, 'content': 'Has text'},
            partial=True,
            context={'request': request},
        )
        # author without view-all cannot assign to someone else
        self.assertFalse(ok.is_valid())
