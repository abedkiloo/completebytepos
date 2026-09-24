"""Create Delivery Driver users from the field-sales / dispatch board."""

from datetime import date

from django.contrib.auth.models import User
from rest_framework import status

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_DELIVERY_AGENT
from daily_notes.models import DailyNote
from dispatch.driver_create import (
    generate_temp_password,
    slug_username,
    split_display_name,
    unique_username,
)
from delivery.tests.test_claim_and_drivers import ClaimAndDriversAPITestCase


class CreateDriverAPITestCase(ClaimAndDriversAPITestCase):
    def test_dispatch_creates_driver_and_lists_them(self):
        self._auth(self.dispatch)
        res = self.client.post(
            '/api/dispatch/drivers/',
            {'display_name': 'Ken Mutua', 'phone': '0712345678'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data['display_name'], 'Ken Mutua')
        self.assertTrue(res.data['username'])
        self.assertTrue(res.data['temporary_password'])
        self.assertEqual(res.data['phone_number'], '254712345678')
        created_id = res.data['id']
        user = User.objects.get(pk=created_id)
        self.assertEqual(user.profile.custom_role.name, ROLE_DELIVERY_AGENT)
        self.assertTrue(user.profile.must_change_password)

        listed = self.client.get('/api/dispatch/drivers/')
        ids = {row['id'] for row in listed.data}
        self.assertIn(created_id, ids)

    def test_create_driver_rejects_invalid_phone_and_blank_name(self):
        self._auth(self.dispatch)
        bad_phone = self.client.post(
            '/api/dispatch/drivers/',
            {'display_name': 'Ken', 'phone': '12'},
            format='json',
        )
        self.assertEqual(bad_phone.status_code, status.HTTP_400_BAD_REQUEST)
        blank = self.client.post(
            '/api/dispatch/drivers/',
            {'display_name': '  ', 'phone': '0712345678'},
            format='json',
        )
        self.assertEqual(blank.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sales_cannot_create_driver(self):
        self._auth(self.sales)
        res = self.client.post(
            '/api/dispatch/drivers/',
            {'display_name': 'No', 'phone': '0712345678'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_explicit_username_and_password(self):
        self._auth(self.dispatch)
        res = self.client.post(
            '/api/dispatch/drivers/',
            {
                'display_name': 'Solo',
                'phone': '0722000111',
                'username': 'drv_solo',
                'password': 'secret99',
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data['username'], 'drv_solo')
        self.assertEqual(res.data['temporary_password'], 'secret99')
        dup = self.client.post(
            '/api/dispatch/drivers/',
            {
                'display_name': 'Solo Two',
                'phone': '0722000112',
                'username': 'drv_solo',
            },
            format='json',
        )
        self.assertEqual(dup.status_code, status.HTTP_400_BAD_REQUEST)

    def test_helpers_split_slug_and_unique_username(self):
        self.assertEqual(split_display_name('Jane Wambua Kariuki')[0], 'Jane')
        self.assertEqual(split_display_name('Jane Wambua Kariuki')[1], 'Wambua Kariuki')
        self.assertEqual(split_display_name('Solo'), ('Solo', ''))
        self.assertEqual(split_display_name('  '), ('', ''))
        self.assertEqual(slug_username('Ken Mutua!'), 'kenmutua')
        self.assertEqual(slug_username('@@@'), 'driver')
        User.objects.create_user('driver', password='x')
        User.objects.create_user('driver2', password='x')
        self.assertEqual(unique_username('@@@'), 'driver3')
        pwd = generate_temp_password()
        self.assertGreaterEqual(len(pwd), 6)

    def test_password_too_short_and_blank_username(self):
        self._auth(self.dispatch)
        short = self.client.post(
            '/api/dispatch/drivers/',
            {
                'display_name': 'Ken',
                'phone': '0712345678',
                'password': 'ab',
            },
            format='json',
        )
        self.assertEqual(short.status_code, status.HTTP_400_BAD_REQUEST)
        blank_user = self.client.post(
            '/api/dispatch/drivers/',
            {
                'display_name': 'Ken Two',
                'phone': '0712345679',
                'username': '  ',
                'password': '   ',
            },
            format='json',
        )
        self.assertEqual(blank_user.status_code, status.HTTP_201_CREATED, blank_user.data)

    def test_delivery_driver_role_missing_raises(self):
        from unittest.mock import patch
        from rest_framework.serializers import ValidationError
        from dispatch.driver_create import delivery_driver_role, generate_temp_password

        with patch('dispatch.driver_create.Role.objects.filter') as mock_filter:
            mock_filter.return_value.first.return_value = None
            with patch('dispatch.driver_create.sync_default_roles'):
                with self.assertRaises(ValidationError):
                    delivery_driver_role()

        with patch('dispatch.driver_create.validate_new_password', side_effect=['bad', None]):
            self.assertTrue(generate_temp_password())

    def test_validate_password_blank_returns_empty(self):
        from dispatch.driver_create import CreateDriverSerializer
        ser = CreateDriverSerializer()
        self.assertEqual(ser.validate_password('   '), '')
        from dispatch.driver_create import driver_payload
        user = User.objects.create_user('orphan_drv', password='x')
        data = driver_payload(user)
        self.assertEqual(data['display_name'], 'orphan_drv')
        self.assertEqual(data['phone_number'], '')
        self.assertEqual(data['role_name'], '')


class StickyDailyNoteAPITests(ClaimAndDriversAPITestCase):
    """Reuse delivery fixture users; manager-like dispatcher is not daily-notes.

    Sticky blocking is authenticated-only so a driver can tick their note.
    """

    def test_blocking_sticky_note_must_be_ticked(self):
        from daily_notes.tests.test_views import _seed_daily_notes_module
        from settings.models import ModuleSettings

        ModuleSettings.objects.update_or_create(
            module_name='daily_notes', defaults={'is_enabled': True},
        )
        _seed_daily_notes_module()
        note = DailyNote.objects.create(
            note_date=date.today(),
            title='Cash short',
            content='Explain the till variance before selling.',
            is_sticky=True,
            author=self.dispatch,
            assigned_to=self.driver,
        )
        DailyNote.objects.create(
            note_date=date.today(),
            content='General handover',
            is_sticky=False,
            author=self.dispatch,
        )
        self._auth(self.driver)
        blocking = self.client.get('/api/daily-notes/notes/blocking/')
        self.assertEqual(blocking.status_code, status.HTTP_200_OK, blocking.data)
        ids = {row['id'] for row in blocking.data}
        self.assertEqual(ids, {note.id})

        tick = self.client.post(f'/api/daily-notes/notes/{note.id}/toggle-done/')
        self.assertEqual(tick.status_code, status.HTTP_200_OK, tick.data)
        self.assertTrue(tick.data['is_done'])
        empty = self.client.get('/api/daily-notes/notes/blocking/')
        self.assertEqual(empty.data, [])

        # General notes do not block.
        self._auth(self.dispatch)
        other = self.client.get('/api/daily-notes/notes/blocking/')
        self.assertEqual(other.data, [])
