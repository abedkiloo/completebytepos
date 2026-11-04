"""Priority field + catalog feature gates for daily notes/tasks."""

from __future__ import annotations

from datetime import date

from rest_framework import status

from daily_notes.models import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MEDIUM, DailyNote, DailyTask
from daily_notes.module_settings import (
    daily_notes_checklists_enabled,
    daily_notes_priority_enabled,
    daily_notes_sticky_enabled,
    daily_notes_tasks_enabled,
)
from settings.models import ModuleFeature, ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase


def _set_feature(module_name: str, feature_key: str, enabled: bool) -> None:
    module, _ = ModuleSettings.objects.get_or_create(
        module_name=module_name,
        defaults={'is_enabled': True},
    )
    module.is_enabled = True
    module.save(update_fields=['is_enabled'])
    feat, _ = ModuleFeature.objects.get_or_create(
        module=module,
        feature_key=feature_key,
        defaults={'feature_name': feature_key, 'is_enabled': enabled},
    )
    feat.is_enabled = enabled
    feat.save(update_fields=['is_enabled'])


class DailyNotesPriorityFeatureTests(ManagerAPITestCase):
    def test_feature_helpers_follow_catalog(self):
        _set_feature('daily_notes', 'note_priority', True)
        self.assertTrue(daily_notes_priority_enabled())
        _set_feature('daily_notes', 'note_priority', False)
        self.assertFalse(daily_notes_priority_enabled())

        _set_feature('daily_notes', 'daily_tasks', False)
        self.assertFalse(daily_notes_tasks_enabled())
        _set_feature('daily_notes', 'checklists', False)
        self.assertFalse(daily_notes_checklists_enabled())
        _set_feature('daily_notes', 'sticky_notes', False)
        self.assertFalse(daily_notes_sticky_enabled())

    def test_create_note_with_high_priority(self):
        _set_feature('daily_notes', 'note_priority', True)
        resp = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'title': 'Hot',
                'content': 'Urgent stock issue',
                'priority': PRIORITY_HIGH,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['priority'], PRIORITY_HIGH)

    def test_priority_forced_medium_when_feature_off(self):
        _set_feature('daily_notes', 'note_priority', False)
        resp = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'title': 'Ignored high',
                'content': 'Should land medium',
                'priority': PRIORITY_HIGH,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['priority'], PRIORITY_MEDIUM)
        note = DailyNote.objects.get(pk=resp.data['id'])
        self.assertEqual(note.priority, PRIORITY_MEDIUM)

    def test_sticky_forced_off_when_feature_disabled(self):
        _set_feature('daily_notes', 'sticky_notes', False)
        _set_feature('daily_notes', 'note_priority', True)
        resp = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'content': 'Not sticky',
                'is_sticky': True,
                'assigned_to': self.manager_user.id,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertFalse(resp.data['is_sticky'])

    def test_checklist_stripped_when_feature_off(self):
        _set_feature('daily_notes', 'checklists', False)
        resp = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'content': 'No checklist package',
                'checklist_items': [{'label': 'Count till', 'is_done': False}],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        note = DailyNote.objects.get(pk=resp.data['id'])
        self.assertEqual(note.checklist_items.count(), 0)

    def test_update_note_priority_and_task_priority(self):
        _set_feature('daily_notes', 'note_priority', True)
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Edit me',
            author=self.manager_user,
            priority=PRIORITY_MEDIUM,
        )
        patched = self.client.patch(
            f'/api/daily-notes/notes/{note.id}/',
            {'priority': PRIORITY_LOW},
            format='json',
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK, patched.data)
        self.assertEqual(patched.data['priority'], PRIORITY_LOW)

        task = self.client.post(
            '/api/daily-notes/tasks/',
            {
                'task_date': str(date.today()),
                'title': 'Prioritised task',
                'priority': PRIORITY_HIGH,
            },
            format='json',
        )
        self.assertEqual(task.status_code, status.HTTP_201_CREATED, task.data)
        self.assertEqual(task.data['priority'], PRIORITY_HIGH)

        _set_feature('daily_notes', 'note_priority', False)
        task_id = task.data['id']
        forced = self.client.patch(
            f'/api/daily-notes/tasks/{task_id}/',
            {'priority': PRIORITY_HIGH},
            format='json',
        )
        self.assertEqual(forced.status_code, status.HTTP_200_OK, forced.data)
        self.assertEqual(DailyTask.objects.get(pk=task_id).priority, PRIORITY_MEDIUM)
