from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from daily_notes.models import DailyTask


class DailyTaskModelTests(TestCase):
    def test_mark_done_and_clear(self):
        user = User.objects.create_user('u', password='x')
        task = DailyTask.objects.create(
            task_date=date.today(),
            title='Test',
            author=user,
            assigned_to=user,
        )
        at = timezone.now()
        task.mark_done(done=True, at=at)
        self.assertTrue(task.is_done)
        self.assertEqual(task.completed_at, at)
        task.mark_done(done=False)
        self.assertFalse(task.is_done)
        self.assertIsNone(task.completed_at)

    def test_str_representation(self):
        user = User.objects.create_user('u2', password='x')
        task = DailyTask.objects.create(
            task_date=date.today(),
            title='Shelf check',
            author=user,
            assigned_to=user,
            is_done=True,
        )
        self.assertIn('done', str(task))
