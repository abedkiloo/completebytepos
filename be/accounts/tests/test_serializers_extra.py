"""Serializer edge-path coverage for accounts."""

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from rest_framework.exceptions import ValidationError

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ensure_permissions, sync_default_roles
from accounts.serializers import (
    RoleListSerializer,
    RoleSerializer,
    UserCreateSerializer,
    UserProfileSerializer,
    UserSerializer,
)


class AccountsSerializerExtraTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.admin = User.objects.create_superuser('ser_admin', 's@t.com', 'x')
        UserProfile.objects.create(user=cls.admin, role='super_admin', is_active=True)
        cls.role = Role.objects.get(name=ROLE_MANAGER)

    def test_role_serializer_create_update_with_permissions(self):
        perms = list(Permission.objects.all()[:2])
        ser = RoleSerializer(
            data={
                'name': 'Ser Role',
                'description': 'd',
                'permission_ids': [p.id for p in perms],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        role = ser.save()
        self.assertEqual(role.permissions.count(), 2)
        ser = RoleSerializer(
            role,
            data={'permission_ids': [perms[0].id], 'description': 'u'},
            partial=True,
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        role = ser.save()
        self.assertEqual(role.permissions.count(), 1)
        data = RoleSerializer(role).data
        self.assertEqual(data['permissions_count'], 1)
        self.assertEqual(RoleListSerializer(role).data['permissions_count'], 1)

    def test_user_serializer_create_update_password(self):
        ser = UserSerializer(
            data={
                'username': 'ser_new',
                'password': 'pass1234',
                'email': 'n@t.com',
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        user = ser.save()
        self.assertTrue(user.check_password('pass1234'))

        request = RequestFactory().patch('/')
        request.user = self.admin
        ser = UserSerializer(
            user,
            data={'password': 'pass9999'},
            partial=True,
            context={'request': request},
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        user = ser.save()
        self.assertTrue(user.check_password('pass9999'))

        ser = UserSerializer(data={'username': 'x', 'password': '12'})
        self.assertFalse(ser.is_valid())

        # empty password treated as None
        ser = UserSerializer()
        self.assertIsNone(ser.validate_password(''))

    def test_user_create_serializer(self):
        request = RequestFactory().post('/')
        request.user = self.admin
        ser = UserCreateSerializer(
            data={
                'username': 'created_ser',
                'password': 'pass1234',
                'email': 'c@t.com',
                'role': 'cashier',
                'custom_role_id': self.role.id,
                'phone_number': '',
            },
            context={'request': request},
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        user = ser.save()
        self.assertTrue(user.profile.must_change_password)
        self.assertEqual(user.profile.custom_role_id, self.role.id)

        ser = UserCreateSerializer(
            data={'username': 'bad', 'password': '1'},
            context={'request': request},
        )
        self.assertFalse(ser.is_valid())

    def test_profile_phone_and_permissions_list(self):
        profile = self.admin.profile
        ser = UserProfileSerializer(instance=profile, data={'phone_number': ''}, partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        data = UserSerializer(self.admin).data
        self.assertIn('permissions', data)
        self.assertTrue(isinstance(data['permissions'], list))
