"""Unit tests for daily notes access helpers."""

from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.test import TestCase

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, ensure_permissions, sync_default_roles
from daily_notes.access import (
    _user_has_perm,
    user_may_access_daily_notes,
    user_may_view_all_daily_notes,
)
from settings.models import ModuleSetting


def _seed_flags(**overrides):
    cache.clear()
    defaults = {
        'allow_sales_access': True,
        'allow_manager_view_all': True,
        'allow_sales_view_all': False,
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        ModuleSetting.objects.update_or_create(
            module='daily_notes',
            key=key,
            defaults={
                'label': key,
                'description': '',
                'default_value': value,
                'value': value,
            },
        )


class DailyNotesAccessUnitTests(TestCase):
    def setUp(self):
        ensure_permissions()
        sync_default_roles()
        _seed_flags()
        self.manager = User.objects.create_user('mgr_a', password='x')
        self.sales = User.objects.create_user('sales_a', password='x')
        self.no_profile = User.objects.create_user('orphan', password='x')
        UserProfile.objects.create(
            user=self.manager,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
        )
        UserProfile.objects.create(
            user=self.sales,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
        )

    def test_anonymous_cannot_access(self):
        anon = AnonymousUser()
        self.assertFalse(getattr(anon, 'is_authenticated', False))
        self.assertFalse(user_may_access_daily_notes(anon))
        self.assertFalse(user_may_view_all_daily_notes(anon))
        self.assertFalse(_user_has_perm(None, 'daily_notes', 'view'))

    def test_user_without_profile_denied(self):
        self.assertFalse(user_may_access_daily_notes(self.no_profile))
        self.assertFalse(user_may_view_all_daily_notes(self.no_profile))

    def test_superuser_has_perm_via_user_has_perm_branch(self):
        admin = User.objects.create_superuser('su2', password='x')
        self.assertTrue(user_may_access_daily_notes(admin))

    def test_superuser_always_allowed(self):
        admin = User.objects.create_superuser('su', password='x')
        self.assertTrue(_user_has_perm(admin, 'daily_notes', 'view'))
        self.assertTrue(user_may_access_daily_notes(admin))
        self.assertTrue(user_may_view_all_daily_notes(admin))

    def test_sales_allowed_when_module_flag_on(self):
        self.assertTrue(user_may_access_daily_notes(self.sales))

    def test_sales_blocked_when_module_flag_off(self):
        _seed_flags(allow_sales_access=False)
        self.assertFalse(user_may_access_daily_notes(self.sales))

    def test_manager_view_all_when_setting_on(self):
        self.assertTrue(user_may_view_all_daily_notes(self.manager))

    def test_manager_view_all_off_when_setting_disabled(self):
        _seed_flags(allow_manager_view_all=False)
        self.assertFalse(user_may_view_all_daily_notes(self.manager))

    def test_sales_view_all_only_when_flag_and_setting_on(self):
        self.assertFalse(user_may_view_all_daily_notes(self.sales))
        _seed_flags(allow_sales_view_all=True)
        self.assertFalse(user_may_view_all_daily_notes(self.sales))
        role = Role.objects.get(name=ROLE_SALES)
        role.permissions.add(
            Permission.objects.get(module='daily_notes', action='view_all')
        )
        self.assertTrue(user_may_view_all_daily_notes(self.sales))

    def test_super_admin_role_may_view_all(self):
        admin_user = User.objects.create_user('sa', password='x')
        UserProfile.objects.create(
            user=admin_user,
            role='super_admin',
            custom_role=Role.objects.get(name='Super Admin'),
        )
        self.assertTrue(user_may_view_all_daily_notes(admin_user))
