"""API tests: user update with profile fields and empty password."""

from django.core.cache import cache
from django.contrib.auth.models import User
from django.test import TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserProfile, Role


class UserProfileUpdateAPITests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123',
        )
        UserProfile.objects.create(user=self.superuser, role='super_admin', is_active=True)

        self.target = User.objects.create_user(
            username='manager',
            email='manager@test.com',
            password='manager123',
            first_name='Lawrence',
            last_name='Kinahunzu',
        )
        UserProfile.objects.create(
            user=self.target,
            role='manager',
            phone_number='',
            is_active=True,
        )
        self.custom_role = Role.objects.create(name='Ops Lead', description='Ops')

    def _auth(self):
        token = str(RefreshToken.for_user(self.superuser).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_update_without_password_field_succeeds(self):
        self._auth()
        response = self.client.patch(
            f'/api/accounts/users/{self.target.id}/',
            {
                'first_name': 'Lawrence',
                'last_name': 'Kinahunzu',
                'email': 'manager@test.com',
                'password': '',
                'is_active': True,
                'is_staff': True,
                'role': 'manager',
                'phone_number': '254712345678',
                'custom_role_id': self.custom_role.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.target.refresh_from_db()
        self.target.profile.refresh_from_db()
        self.assertEqual(self.target.profile.phone_number, '254712345678')
        self.assertEqual(self.target.profile.custom_role_id, self.custom_role.id)

    def test_update_phone_only(self):
        self._auth()
        response = self.client.patch(
            f'/api/accounts/users/{self.target.id}/',
            {'phone_number': '254700000001'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target.profile.refresh_from_db()
        self.assertEqual(self.target.profile.phone_number, '254700000001')
