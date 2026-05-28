from django.contrib.auth.models import User
from django.test import TestCase

from settings.setup_status import get_setup_status
from settings.models import ModuleSettings


class SetupStatusTests(TestCase):
    def test_empty_db_needs_install(self):
        status = get_setup_status()
        self.assertTrue(status['needs_install'])
        self.assertFalse(status['installed'])

    def test_users_and_modules_mark_installed(self):
        from django.core.management import call_command

        call_command('init_modules', verbosity=0)
        User.objects.create_user('admin', password='x')
        status = get_setup_status()
        self.assertFalse(status['needs_install'])
        self.assertTrue(status['installed'])
        self.assertGreaterEqual(status['module_count'], ModuleSettings.objects.count())
