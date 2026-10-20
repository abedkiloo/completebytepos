"""Coverage for UserProfile legacy paths, password policy, and users module flags."""

from django.contrib.auth.models import User
from django.test import TestCase
from unittest.mock import patch

from accounts.models import Permission, Role, UserProfile
from accounts.module_settings import (
    apply_profile_representation_flags,
    apply_user_representation_flags,
    validate_user_write,
)
from accounts.password_policy import (
    set_must_change_password,
    user_must_change_password,
    validate_new_password,
)
from accounts.role_definitions import ensure_permissions, sync_default_roles


class UserProfileLegacyPermissionTests(TestCase):
    def test_str_and_legacy_admin_paths(self):
        user = User.objects.create_user('legacy_admin', password='x', is_staff=True)
        profile = UserProfile.objects.create(user=user, role='admin', is_active=True)
        self.assertIn('legacy_admin', str(profile))
        self.assertTrue(profile.is_admin)
        self.assertTrue(profile.is_manager)
        self.assertTrue(profile.has_permission('products', 'view'))
        self.assertTrue(profile.has_permission('users', 'view'))
        self.assertFalse(profile.has_permission('users', 'delete'))
        self.assertTrue(profile.has_module_access('sales'))
        self.assertEqual(list(profile.get_all_permissions()), [])

    def test_legacy_manager_and_cashier(self):
        mgr = User.objects.create_user('legacy_mgr', password='x')
        mgr_p = UserProfile.objects.create(user=mgr, role='manager', is_active=True)
        self.assertTrue(mgr_p.has_permission('sales', 'view'))
        self.assertFalse(mgr_p.has_permission('users', 'view'))
        self.assertTrue(mgr_p.has_module_access('products'))
        self.assertFalse(mgr_p.has_module_access('settings'))

        cash = User.objects.create_user('legacy_cash', password='x')
        cash_p = UserProfile.objects.create(user=cash, role='cashier', is_active=True)
        self.assertTrue(cash_p.has_permission('sales', 'create'))
        self.assertFalse(cash_p.has_permission('sales', 'delete'))
        self.assertFalse(cash_p.has_permission('expenses', 'view'))
        self.assertTrue(cash_p.has_module_access('pos'))
        self.assertFalse(cash_p.has_module_access('reports'))

    def test_suppliers_legacy_branch_and_unknown_role(self):
        # Role already handled above; exercise suppliers special-case fallthrough
        # with a non-standard role string that hits the suppliers block then False.
        user = User.objects.create_user('odd_role', password='x')
        profile = UserProfile.objects.create(user=user, role='cashier', is_active=True)
        self.assertFalse(profile.has_permission('suppliers', 'view'))

        unknown = User.objects.create_user('unknown_role', password='x')
        # role choices may reject unknown — use cashier then clear custom and poke method
        up = UserProfile.objects.create(user=unknown, role='cashier', is_active=True)
        up.role = 'field_agent'  # may not be in choices but stored if not validated
        # Force role that falls through legacy switch
        UserProfile.objects.filter(pk=up.pk).update(role='other')
        up.refresh_from_db()
        self.assertFalse(up.has_permission('products', 'view'))
        self.assertFalse(up.has_module_access('products'))

    def test_super_admin_get_all_permissions(self):
        ensure_permissions()
        user = User.objects.create_superuser('sa_all', 'a@t.com', 'x')
        profile = UserProfile.objects.create(user=user, role='super_admin', is_active=True)
        self.assertEqual(profile.get_all_permissions().count(), Permission.objects.count())


class PasswordPolicyTests(TestCase):
    def test_user_must_change_password(self):
        user = User.objects.create_user('pw_user', password='secret1')
        self.assertFalse(user_must_change_password(user))
        set_must_change_password(user, True)
        user.refresh_from_db()
        self.assertTrue(user_must_change_password(user))
        set_must_change_password(user, True)  # no-op same value
        set_must_change_password(user, False)

    def test_set_must_change_creates_profile(self):
        user = User.objects.create_user('pw_bare', password='secret1')
        set_must_change_password(user, True)
        self.assertTrue(user.profile.must_change_password)

    def test_validate_new_password(self):
        self.assertIsNotNone(validate_new_password(None))
        self.assertIsNotNone(validate_new_password(''))
        self.assertIsNotNone(validate_new_password('123'))
        user = User.objects.create_user('pw_reuse', password='samepass')
        self.assertIsNotNone(
            validate_new_password('samepass', user=user, reject_reuse=True)
        )
        self.assertIsNone(validate_new_password('newpass1'))


class UsersModuleFlagsTests(TestCase):
    @patch('accounts.module_settings.users_show_phone', return_value=False)
    @patch('accounts.module_settings.users_show_status', return_value=False)
    @patch('accounts.module_settings.users_enable_inline_role_assignment', return_value=False)
    def test_apply_profile_flags(self, *_mocks):
        data = apply_profile_representation_flags(
            {
                'phone_number': '1',
                'is_active': True,
                'custom_role': {},
                'custom_role_id': 1,
                'keep': True,
            }
        )
        self.assertNotIn('phone_number', data)
        self.assertNotIn('is_active', data)
        self.assertNotIn('custom_role', data)
        self.assertTrue(data['keep'])

    @patch('accounts.module_settings.users_show_email', return_value=False)
    @patch('accounts.module_settings.users_show_full_name', return_value=False)
    @patch('accounts.module_settings.users_show_status', return_value=False)
    @patch('accounts.module_settings.users_show_date_joined', return_value=False)
    @patch('accounts.module_settings.users_show_staff_flag', return_value=False)
    @patch('accounts.module_settings.apply_profile_representation_flags', side_effect=lambda d: d)
    def test_apply_user_flags(self, *_mocks):
        data = apply_user_representation_flags(
            {
                'email': 'a@b.com',
                'first_name': 'A',
                'last_name': 'B',
                'is_active': True,
                'date_joined': 'x',
                'is_staff': True,
                'profile': {'phone_number': '1'},
            }
        )
        self.assertNotIn('email', data)
        self.assertNotIn('first_name', data)
        self.assertIn('profile', data)

    @patch('accounts.module_settings.users_show_email', return_value=False)
    @patch('accounts.module_settings.users_show_full_name', return_value=False)
    @patch('accounts.module_settings.users_show_status', return_value=False)
    @patch('accounts.module_settings.users_show_staff_flag', return_value=False)
    @patch('accounts.module_settings.users_enable_inline_role_assignment', return_value=False)
    @patch('accounts.module_settings.users_show_phone', return_value=False)
    def test_validate_user_write(self, *_mocks):
        attrs = validate_user_write(
            {
                'email': 'a@b.com',
                'first_name': 'A',
                'last_name': 'B',
                'is_active': True,
                'is_staff': True,
                'role': 'manager',
                'custom_role_id': 1,
                'phone_number': '0711',
                'username': 'keep',
            }
        )
        self.assertEqual(attrs, {'username': 'keep'})
