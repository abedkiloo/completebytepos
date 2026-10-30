"""Redeploy must not wipe a changed admin password back to admin123."""

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings

from accounts.models import UserProfile
from accounts.role_definitions import ensure_permissions, sync_default_roles


class CreateUsersPreservesPasswordTests(TestCase):
    def setUp(self):
        ensure_permissions()
        sync_default_roles()

    def test_second_run_keeps_changed_admin_password(self):
        call_command('create_users', verbosity=0)
        admin = User.objects.get(username='admin')
        self.assertTrue(admin.check_password('admin123'))

        admin.set_password('Omuwenga@77')
        admin.save()
        self.assertTrue(admin.check_password('Omuwenga@77'))

        call_command('create_users', verbosity=0)
        admin.refresh_from_db()
        self.assertTrue(admin.check_password('Omuwenga@77'))
        self.assertFalse(admin.check_password('admin123'))

    def test_reset_passwords_flag_restores_defaults(self):
        call_command('create_users', verbosity=0)
        admin = User.objects.get(username='admin')
        admin.set_password('Omuwenga@77')
        admin.save()

        call_command('create_users', '--reset-passwords', verbosity=0)
        admin.refresh_from_db()
        self.assertTrue(admin.check_password('admin123'))

    @override_settings()
    def test_env_password_used_on_first_create_only(self):
        User.objects.filter(username='admin').delete()
        UserProfile.objects.filter(user__username='admin').delete()
        with self.settings():
            import os

            os.environ['BOOTSTRAP_ADMIN_PASSWORD'] = 'EnvPass@99'
            try:
                call_command('create_users', verbosity=0)
                admin = User.objects.get(username='admin')
                self.assertTrue(admin.check_password('EnvPass@99'))

                admin.set_password('LaterPass@11')
                admin.save()
                call_command('create_users', verbosity=0)
                admin.refresh_from_db()
                self.assertTrue(admin.check_password('LaterPass@11'))
            finally:
                os.environ.pop('BOOTSTRAP_ADMIN_PASSWORD', None)
