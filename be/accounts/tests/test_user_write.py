"""Unit tests for accounts.user_write helpers."""

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import UserProfile, Role
from accounts.user_write import prepare_user_write_data, apply_profile_updates


class PrepareUserWriteDataTests(TestCase):
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
        apply_profile_updates(self.user, {'role': 'cashier', 'phone_number': '123'})
        self.user.refresh_from_db()
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertEqual(self.user.profile.phone_number, '123')

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

    def test_no_op_when_profile_data_empty(self):
        UserProfile.objects.create(user=self.user, role='cashier')
        apply_profile_updates(self.user, {})
        self.assertEqual(self.user.profile.role, 'cashier')
