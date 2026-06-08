from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from daily_notes.models import DailyNote
from daily_notes.serializers import DailyNoteSerializer


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
