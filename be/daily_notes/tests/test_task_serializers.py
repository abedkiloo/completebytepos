from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from daily_notes.models import DailyTask
from daily_notes.serializers import DailyTaskSerializer


class DailyTaskSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tasker', password='x')

    def test_create_open_task(self):
        ser = DailyTaskSerializer(
            data={
                'task_date': str(date.today()),
                'title': 'Open shelves',
                'description': '',
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        task = ser.save(author=self.user)
        self.assertFalse(task.is_done)
        self.assertIsNone(task.completed_at)
        self.assertEqual(task.assigned_to_id, self.user.id)

    def test_create_done_task_sets_completed_at(self):
        ser = DailyTaskSerializer(
            data={
                'task_date': str(date.today()),
                'title': 'Done already',
                'is_done': True,
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        task = ser.save(author=self.user)
        self.assertTrue(task.is_done)
        self.assertIsNotNone(task.completed_at)

    def test_update_clears_completed_at_when_reopened(self):
        task = DailyTask.objects.create(
            task_date=date.today(),
            title='Was done',
            is_done=True,
            completed_at=timezone.now(),
            author=self.user,
            assigned_to=self.user,
        )
        ser = DailyTaskSerializer(task, data={'is_done': False}, partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        updated = ser.save()
        self.assertFalse(updated.is_done)
        self.assertIsNone(updated.completed_at)

    def test_done_requires_title_and_assign_self_only(self):
        ser = DailyTaskSerializer(
            data={'task_date': str(date.today()), 'title': '', 'is_done': True}
        )
        self.assertFalse(ser.is_valid())
        other = User.objects.create_user('other_t', password='x')
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.post('/api/daily-notes/tasks/')
        request.user = self.user
        blocked = DailyTaskSerializer(
            data={
                'task_date': str(date.today()),
                'title': 'For someone else',
                'assigned_to': other.id,
            },
            context={'request': request},
        )
        self.assertFalse(blocked.is_valid())
        task = DailyTask.objects.create(
            task_date=date.today(),
            title='Stay',
            author=self.user,
            assigned_to=self.user,
        )
        moved = DailyTaskSerializer(
            task,
            data={'assigned_to': self.user.id, 'title': 'Stay', 'is_done': True},
            partial=True,
        )
        self.assertTrue(moved.is_valid(), moved.errors)
        saved = moved.save()
        self.assertTrue(saved.is_done)
        ser2 = DailyTaskSerializer()
        ser2._apply_completion(saved, True)
        self.assertTrue(saved.is_done)
