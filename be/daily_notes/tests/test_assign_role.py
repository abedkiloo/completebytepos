"""Assign a daily note to one person or every user on a role."""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework import serializers, status

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_DELIVERY_AGENT, ROLE_SALES, sync_default_roles
from daily_notes.models import DailyNote
from daily_notes.services import (
    active_staff_users,
    create_notes_for_assignees,
    users_with_role,
)
from daily_notes.tests.test_views import _seed_daily_notes_module
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class AssignNoteToRoleAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()
        self.sales_role = Role.objects.get(name=ROLE_SALES)
        self.driver_role = Role.objects.get(name=ROLE_DELIVERY_AGENT)
        self.ann = User.objects.create_user('ann_sales', password='x', first_name='Ann')
        self.ken = User.objects.create_user('ken_sales', password='x', first_name='Ken')
        UserProfile.objects.create(user=self.ann, role='cashier', custom_role=self.sales_role)
        UserProfile.objects.create(user=self.ken, role='cashier', custom_role=self.sales_role)

    def test_users_with_role_empty_for_none(self):
        self.assertEqual(users_with_role(None), [])

    def test_create_notes_for_person_and_unassigned(self):
        person = create_notes_for_assignees(
            author=self.manager_user,
            note_date=date.today(),
            content='For Ann only',
            assigned_to=self.ann,
        )
        self.assertEqual(len(person), 1)
        self.assertEqual(person[0].assigned_to_id, self.ann.id)
        general = create_notes_for_assignees(
            author=self.manager_user,
            note_date=date.today(),
            content='Shop log',
            is_done=True,
        )
        self.assertEqual(len(general), 1)
        self.assertIsNone(general[0].assigned_to_id)
        self.assertTrue(general[0].is_done)
        none_in_role = create_notes_for_assignees(
            author=self.manager_user,
            note_date=date.today(),
            content='Nobody',
            assigned_role=self.driver_role,
        )
        self.assertEqual(none_in_role, [])
        sticky_self = create_notes_for_assignees(
            author=self.manager_user,
            note_date=date.today(),
            content='Block me',
            is_sticky=True,
        )
        self.assertEqual(sticky_self[0].assigned_to_id, self.manager_user.id)
        everyone = create_notes_for_assignees(
            author=self.manager_user,
            note_date=date.today(),
            content='All staff briefing',
            assign_to_all=True,
        )
        self.assertEqual(len(everyone), len(active_staff_users()))
        self.assertTrue(all(n.assigned_to_id for n in everyone))

    def test_manager_assigns_sticky_to_role(self):
        response = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'title': 'Till',
                'content': 'Count before you sell',
                'is_sticky': True,
                'assigned_role': self.sales_role.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['created_count'], 2)
        self.assertEqual(response.data['assigned_role'], self.sales_role.id)
        self.assertEqual(response.data['assigned_role_name'], ROLE_SALES)
        copies = DailyNote.objects.filter(assignment_group=response.data['assignment_group'])
        self.assertEqual(copies.count(), 2)
        assignees = {n.assigned_to_id for n in copies}
        self.assertEqual(assignees, {self.ann.id, self.ken.id})

        self.client.force_authenticate(self.ann)
        blocking = self.client.get('/api/daily-notes/notes/blocking/')
        self.assertEqual(len(blocking.data), 1)
        self.assertEqual(blocking.data[0]['assigned_role_name'], ROLE_SALES)

    def test_cannot_send_person_and_role(self):
        response = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'content': 'Pick one',
                'is_sticky': True,
                'assigned_to': self.ann.id,
                'assigned_role': self.sales_role.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_role_is_rejected(self):
        response = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'content': 'No drivers yet',
                'is_sticky': True,
                'assigned_role': self.driver_role.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_roles_list_and_general_note_for_person(self):
        roles = self.client.get('/api/daily-notes/notes/roles/')
        self.assertEqual(roles.status_code, status.HTTP_200_OK)
        names = {row['name'] for row in roles.data}
        self.assertIn(ROLE_SALES, names)
        created = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'content': 'Handover for Ann',
                'is_sticky': False,
                'assigned_to': self.ann.id,
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(created.data['assigned_to'], self.ann.id)
        self.assertEqual(created.data.get('created_count', 1), 1)

    def test_sticky_without_assignee_requires_person_or_role(self):
        response = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'content': 'Must assign',
                'is_sticky': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_assigned_role_and_sticky_defaults_assignee(self):
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Count before you sell',
            is_sticky=True,
            author=self.manager_user,
            assigned_to=self.ann,
            assigned_role=self.sales_role,
        )
        patched = self.client.patch(
            f'/api/daily-notes/notes/{note.id}/',
            {'assigned_role': self.sales_role.id, 'content': 'Count before you sell'},
            format='json',
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK, patched.data)
        self.assertEqual(patched.data['assigned_role'], self.sales_role.id)
        from daily_notes.serializers import DailyNoteSerializer

        note.assigned_to = None
        note.assigned_role = None
        DailyNoteSerializer().update(note, {})
        self.assertEqual(note.assigned_to_id, self.manager_user.id)

    def test_create_errors_when_fanout_returns_nothing(self):
        from daily_notes.serializers import DailyNoteSerializer
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.post('/api/daily-notes/notes/')
        request.user = self.manager_user
        ser = DailyNoteSerializer(
            data={
                'note_date': str(date.today()),
                'content': 'Handover for Ann',
                'assigned_to': self.ann.id,
            },
            context={'request': request},
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        with patch('daily_notes.serializers.create_notes_for_assignees', return_value=[]):
            with self.assertRaises(serializers.ValidationError):
                ser.save(author=self.manager_user)


    def test_manager_assigns_note_to_everyone(self):
        before = User.objects.filter(is_active=True).count()
        response = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'title': 'Shop-wide',
                'content': 'Power cut at 3pm — close tills',
                'is_sticky': True,
                'assign_to_all': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['created_count'], before)
        copies = DailyNote.objects.filter(content='Power cut at 3pm — close tills')
        self.assertEqual(copies.count(), before)
        self.assertTrue(all(n.assigned_to_id for n in copies))

        self.client.force_authenticate(self.ann)
        inbox = self.client.get('/api/daily-notes/notes/blocking/')
        self.assertEqual(len(inbox.data), 1)
        self.assertTrue(inbox.data[0]['is_sticky'])

    def test_cannot_send_everyone_and_a_person(self):
        response = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'content': 'Pick one audience',
                'assign_to_all': True,
                'assigned_to': self.ann.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_everyone_rejected_when_no_active_staff(self):
        with patch('daily_notes.serializers.active_staff_users', return_value=[]):
            response = self.client.post(
                '/api/daily-notes/notes/',
                {
                    'note_date': str(date.today()),
                    'content': 'All hands',
                    'assign_to_all': True,
                },
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_errors_when_everyone_fanout_is_empty(self):
        from daily_notes.serializers import DailyNoteSerializer
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.post('/api/daily-notes/notes/')
        request.user = self.manager_user
        ser = DailyNoteSerializer(
            data={
                'note_date': str(date.today()),
                'content': 'All hands',
                'assign_to_all': True,
            },
            context={'request': request},
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        with patch('daily_notes.serializers.create_notes_for_assignees', return_value=[]):
            with self.assertRaises(serializers.ValidationError):
                ser.save(author=self.manager_user)

    def test_update_drops_assign_to_all(self):
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Keep this copy',
            author=self.manager_user,
            assigned_to=self.ann,
        )
        patched = self.client.patch(
            f'/api/daily-notes/notes/{note.id}/',
            {
                'content': 'Keep this copy — edited',
                'assign_to_all': True,
                'assigned_to': self.ken.id,
            },
            format='json',
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK, patched.data)
        self.assertEqual(DailyNote.objects.filter(content='Keep this copy — edited').count(), 1)


class AssignNoteToRoleSalesTests(SalesAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()

    def test_sales_cannot_list_roles(self):
        response = self.client.get('/api/daily-notes/notes/roles/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_cannot_assign_role(self):
        role = Role.objects.get(name=ROLE_SALES)
        response = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'content': 'Block all sales',
                'is_sticky': True,
                'assigned_role': role.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sales_cannot_assign_everyone(self):
        response = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': str(date.today()),
                'content': 'All staff',
                'assign_to_all': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_roles_denied_when_sales_access_off(self):
        from django.core.cache import cache
        from settings.models import ModuleSetting

        ModuleSetting.objects.filter(
            module='daily_notes',
            key='allow_sales_access',
        ).update(value=False)
        cache.clear()
        response = self.client.get('/api/daily-notes/notes/roles/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        staff = self.client.get('/api/daily-notes/notes/staff/')
        self.assertEqual(staff.status_code, status.HTTP_403_FORBIDDEN)
