"""Phase 3 — users module settings gates."""

from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework import status

from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from utils.tests.api_test_base import SuperAdminAPITestCase


def _seed_user_settings():
    cache.clear()
    for key, default in (
        ('show_user_email', True),
        ('show_user_phone', True),
        ('show_user_full_name', True),
        ('show_user_status', True),
        ('show_date_joined', True),
        ('show_user_statistics', True),
        ('show_staff_flag', True),
        ('enable_user_create', True),
        ('enable_user_edit', True),
        ('enable_user_delete', True),
        ('enable_inline_role_assignment', True),
        ('enable_role_create', True),
        ('enable_role_edit', True),
        ('enable_role_delete', True),
        ('enable_permission_catalog', True),
    ):
        ModuleSetting.objects.update_or_create(
            module='users',
            key=key,
            defaults={
                'label': key,
                'description': '',
                'default_value': default,
                'value': default,
            },
        )


class UserModuleSettingsAPITests(SuperAdminAPITestCase):
    base_url = '/api/accounts/users/'

    def setUp(self):
        super().setUp()
        _seed_user_settings()
        self.target = User.objects.create_user(
            username='flagged_user',
            email='flagged@example.com',
            password='pass1234',
            first_name='Flag',
            last_name='User',
        )

    def test_create_forbidden_when_disabled(self):
        SettingsService.set('users', 'enable_user_create', False)
        response = self.client.post(
            self.base_url,
            {
                'username': 'new_user',
                'password': 'pass1234',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_assign_role_forbidden_when_disabled(self):
        SettingsService.set('users', 'enable_inline_role_assignment', False)
        response = self.client.post(
            f'{self.base_url}{self.target.id}/assign_role/',
            {'role_id': 1},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_omits_email_when_hidden(self):
        SettingsService.set('users', 'show_user_email', False)
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', response.data)
        row = next(u for u in rows if u['id'] == self.target.id)
        self.assertNotIn('email', row)

    def test_permission_catalog_forbidden_when_disabled(self):
        SettingsService.set('users', 'enable_permission_catalog', False)
        response = self.client.get('/api/accounts/permissions/by_domain/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
