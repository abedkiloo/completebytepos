"""Daily task API and model behaviour."""

from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, sync_default_roles
from daily_notes.models import DailyNote, DailyTask
from daily_notes.tests.test_views import _seed_daily_notes_module
from settings.models import ModuleSetting, ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class DailyTaskAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()
        self.sales_user = User.objects.create_user('sales_t', password='sales123')
        UserProfile.objects.create(
            user=self.sales_user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
        )
        self.open_task = DailyTask.objects.create(
            task_date=date.today(),
            title='Count drawer',
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        self.done_task = DailyTask.objects.create(
            task_date=date.today(),
            title='Restock',
            is_done=True,
            completed_at=timezone.now(),
            author=self.sales_user,
            assigned_to=self.sales_user,
        )

    def test_manager_lists_all_tasks_for_day(self):
        response = self.client.get(
            '/api/daily-notes/tasks/',
            {'task_date': str(date.today())},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row['id'] for row in response.data.get('results', response.data)}
        self.assertIn(self.open_task.id, ids)
        self.assertIn(self.done_task.id, ids)

    def test_manager_creates_task(self):
        response = self.client.post(
            '/api/daily-notes/tasks/',
            {
                'task_date': str(date.today()),
                'title': 'Clean floor',
                'description': 'Before close',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data['is_done'])
        self.assertIsNone(response.data['completed_at'])

    def test_toggle_done_sets_completed_at(self):
        response = self.client.post(
            f'/api/daily-notes/tasks/{self.open_task.id}/toggle-done/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_done'])
        self.assertIsNotNone(response.data['completed_at'])
        response = self.client.post(
            f'/api/daily-notes/tasks/{self.open_task.id}/toggle-done/'
        )
        self.assertFalse(response.data['is_done'])
        self.assertIsNone(response.data['completed_at'])

    def test_manager_cannot_toggle_other_users_task(self):
        response = self.client.post(
            f'/api/daily-notes/tasks/{self.done_task.id}/toggle-done/'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_recent_dates_includes_task_only_days(self):
        task_day = date.today().replace(day=1)
        DailyTask.objects.create(
            task_date=task_day,
            title='Solo task day',
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        response = self.client.get('/api/daily-notes/notes/recent-dates/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(task_day, response.data['dates'])

    def test_filter_tasks_by_status_open(self):
        response = self.client.get(
            '/api/daily-notes/tasks/',
            {'task_date': str(date.today()), 'status': 'open'},
        )
        rows = response.data.get('results', response.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], self.open_task.id)


class DailyTaskAssignmentTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()
        self.sales_user = User.objects.create_user('sales_assign', password='sales123')
        UserProfile.objects.create(
            user=self.sales_user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
        )

    def test_manager_assigns_task_to_sales_user(self):
        response = self.client.post(
            '/api/daily-notes/tasks/',
            {
                'task_date': str(date.today()),
                'title': 'Verify display',
                'assigned_to': self.sales_user.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['assigned_to'], self.sales_user.id)
        self.assertEqual(response.data['author'], self.manager_user.id)

    def test_pending_lists_open_assigned_tasks(self):
        DailyTask.objects.create(
            task_date=date.today(),
            title='Pending one',
            author=self.manager_user,
            assigned_to=self.sales_user,
        )
        DailyTask.objects.create(
            task_date=date.today(),
            title='Already done',
            is_done=True,
            completed_at=timezone.now(),
            author=self.manager_user,
            assigned_to=self.sales_user,
        )
        self.client.force_authenticate(user=self.sales_user)
        response = self.client.get('/api/daily-notes/tasks/pending/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Pending one')

    def test_sales_toggles_task_assigned_to_them(self):
        task = DailyTask.objects.create(
            task_date=date.today(),
            title='Do this',
            author=self.manager_user,
            assigned_to=self.sales_user,
        )
        self.client.force_authenticate(user=self.sales_user)
        response = self.client.post(f'/api/daily-notes/tasks/{task.id}/toggle-done/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_done'])


class DailyTaskSalesTests(SalesAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()
        self.own = DailyTask.objects.create(
            task_date=date.today(),
            title='My task',
            author=self.sales_user,
            assigned_to=self.sales_user,
        )
        other = User.objects.create_user('mgr_t', password='mgr123')
        UserProfile.objects.create(
            user=other,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
        )
        self.other_task = DailyTask.objects.create(
            task_date=date.today(),
            title='Manager task',
            author=other,
            assigned_to=other,
        )

    def test_sales_sees_only_own_tasks(self):
        response = self.client.get(
            '/api/daily-notes/tasks/',
            {'task_date': str(date.today())},
        )
        rows = response.data.get('results', response.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], self.own.id)

    def test_sales_creates_and_marks_done(self):
        create = self.client.post(
            '/api/daily-notes/tasks/',
            {
                'task_date': str(date.today()),
                'title': 'New task',
                'is_done': True,
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        self.assertTrue(create.data['is_done'])
        self.assertIsNotNone(create.data['completed_at'])
        self.assertEqual(create.data['assigned_to'], self.sales_user.id)

    def test_sales_sees_task_assigned_by_manager(self):
        manager = User.objects.create_user('mgr_assign', password='mgr123')
        UserProfile.objects.create(
            user=manager,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
        )
        DailyTask.objects.create(
            task_date=date.today(),
            title='Assigned by boss',
            author=manager,
            assigned_to=self.sales_user,
        )
        response = self.client.get(
            '/api/daily-notes/tasks/',
            {'task_date': str(date.today())},
        )
        rows = response.data.get('results', response.data)
        titles = {row['title'] for row in rows}
        self.assertIn('Assigned by boss', titles)
