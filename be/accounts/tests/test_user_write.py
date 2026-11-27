"""Unit tests for accounts.user_write helpers."""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from accounts.models import UserProfile, Role
from accounts.user_write import (
    apply_profile_updates,
    custom_role_name,
    prepare_user_write_data,
    strip_privilege_escalation,
)


class PrepareUserWriteDataTests(TestCase):
    def test_accepts_mapping_without_copy(self):
        payload, profile = prepare_user_write_data((('first_name', 'Ann'),))
        self.assertEqual(payload['first_name'], 'Ann')
        self.assertEqual(profile, {})

    def test_strips_blank_password(self):
        payload, profile = prepare_user_write_data({
            'first_name': 'A',
            'password': '',
            'phone_number': '254700000000',
        })
        self.assertNotIn('password', payload)
        self.assertEqual(profile['phone_number'], '254700000000')

    def test_splits_profile_fields(self):
        payload, profile = prepare_user_write_data({
            'email': 'a@b.com',
            'role': 'manager',
            'custom_role_id': 5,
        })
        self.assertEqual(payload['email'], 'a@b.com')
        self.assertEqual(profile['role'], 'manager')
        self.assertEqual(profile['custom_role_id'], 5)

    def test_empty_custom_role_clears_assignment(self):
        _, profile = prepare_user_write_data({'custom_role_id': ''})
        self.assertIn('custom_role', profile)
        self.assertIsNone(profile['custom_role'])


class ApplyProfileUpdatesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='writer',
            email='w@test.com',
            password='pass12345',
        )
        self.role = Role.objects.create(
            name='Store Manager',
            description='Test role',
        )

    def test_creates_profile_when_missing(self):
        apply_profile_updates(self.user, {'role': 'cashier', 'phone_number': '0712345678'})
        self.user.refresh_from_db()
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertEqual(self.user.profile.phone_number, '254712345678')

    def test_updates_role_and_custom_role(self):
        UserProfile.objects.create(user=self.user, role='cashier')
        apply_profile_updates(self.user, {
            'role': 'manager',
            'custom_role_id': self.role.id,
        })
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.role, 'manager')
        self.assertEqual(self.user.profile.custom_role_id, self.role.id)

    def test_clears_custom_role(self):
        UserProfile.objects.create(
            user=self.user,
            role='cashier',
            custom_role=self.role,
        )
        apply_profile_updates(self.user, {'custom_role': None})
        self.user.profile.refresh_from_db()
        self.assertIsNone(self.user.profile.custom_role_id)

    def test_ignores_invalid_custom_role_id(self):
        UserProfile.objects.create(user=self.user, role='cashier')
        apply_profile_updates(self.user, {'custom_role_id': 'not-an-id'})
        self.user.profile.refresh_from_db()
        self.assertIsNone(self.user.profile.custom_role_id)

    def test_invalid_phone_raises(self):
        from rest_framework.exceptions import ValidationError as DrfValidationError

        UserProfile.objects.create(user=self.user, role='cashier')
        with self.assertRaises(DrfValidationError):
            apply_profile_updates(self.user, {'phone_number': 'not-a-phone'})

    def test_no_op_when_profile_data_empty(self):
        UserProfile.objects.create(user=self.user, role='cashier')
        apply_profile_updates(self.user, {})
        self.assertEqual(self.user.profile.role, 'cashier')


class StripPrivilegeAndCustomRoleNameTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user('mgr_write', password='x')
        UserProfile.objects.create(user=self.manager, role='manager')
        self.admin = User.objects.create_superuser('sa_write', 'sa@x.co', 'x')

    def test_custom_role_name_invalid_id_and_missing(self):
        self.assertIsNone(custom_role_name(None))
        self.assertIsNone(custom_role_name(''))
        self.assertIsNone(custom_role_name('not-int'))
        self.assertIsNone(custom_role_name(object()))
        self.assertIsNone(custom_role_name(999999))
        role = Role.objects.create(name='Floor Lead', is_active=True)
        self.assertEqual(custom_role_name(role.id), 'Floor Lead')
        self.assertEqual(custom_role_name(role), 'Floor Lead')

    def test_strip_privilege_rejects_non_admin_escalation(self):
        with self.assertRaises(PermissionDenied):
            strip_privilege_escalation(
                {'is_superuser': True},
                {},
                actor=self.manager,
            )
        with self.assertRaises(PermissionDenied):
            strip_privilege_escalation(
                {},
                {'role': 'super_admin'},
                actor=self.manager,
            )
        sa_role = Role.objects.create(name='Super Admin', is_active=True)
        with self.assertRaises(PermissionDenied):
            strip_privilege_escalation(
                {},
                {'custom_role_id': sa_role.id},
                actor=self.manager,
            )
        # False privilege flags are stripped silently for non-admins.
        cleared = {'is_staff': False, 'is_superuser': 'false'}
        strip_privilege_escalation(cleared, {}, actor=self.manager)
        self.assertNotIn('is_staff', cleared)
        self.assertNotIn('is_superuser', cleared)
        # Super admin may keep privilege fields.
        payload = {'is_staff': True}
        strip_privilege_escalation(payload, {'role': 'super_admin'}, actor=self.admin)
        self.assertTrue(payload['is_staff'])
