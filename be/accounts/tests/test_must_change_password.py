"""Admin-set passwords must be changed on the next login (web and app)."""
from django.core.cache import cache
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserProfile
from settings.models import Tenant, Branch


class MustChangePasswordTestCase(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123',
        )
        UserProfile.objects.create(user=self.admin, role='super_admin', is_active=True)
        Tenant.objects.create(
            name='Test Tenant',
            code='TEST',
            country='Kenya',
            owner=self.admin,
            created_by=self.admin,
        )
        Branch.objects.create(
            tenant=Tenant.objects.get(code='TEST'),
            branch_code='BR001',
            name='Test Branch',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=True,
            created_by=self.admin,
        )
        self.cashier = User.objects.create_user(
            username='cashier1',
            email='cashier@test.com',
            password='temp123',
        )
        self.cashier_profile = UserProfile.objects.create(
            user=self.cashier,
            role='cashier',
            is_active=True,
            must_change_password=True,
        )
        self.client = APIClient()

    def _token(self, user):
        return str(RefreshToken.for_user(user).access_token)

    def _auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self._token(user)}')

    def test_admin_create_user_flags_must_change_password(self):
        self._auth(self.admin)
        response = self.client.post(
            '/api/accounts/users/',
            {
                'username': 'newbie',
                'email': 'newbie@test.com',
                'password': 'welcome1',
                'role': 'cashier',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username='newbie')
        self.assertTrue(user.profile.must_change_password)
        self.assertTrue(response.data['profile']['must_change_password'])

    def test_login_returns_must_change_password(self):
        response = self.client.post(
            '/api/accounts/auth/login/',
            {'username': 'cashier1', 'password': 'temp123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['must_change_password'])
        self.assertTrue(response.data['profile']['must_change_password'])
        self.assertIn('access', response.data)

    def test_flagged_user_cannot_use_other_apis(self):
        self._auth(self.cashier)
        response = self.client.get('/api/accounts/users/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()['error'], 'password_change_required')

    def test_flagged_user_can_load_me(self):
        self._auth(self.cashier)
        response = self.client.get('/api/accounts/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['must_change_password'])

    def test_self_change_clears_flag_and_rejects_reuse(self):
        self._auth(self.cashier)
        reuse = self.client.post(
            f'/api/accounts/users/{self.cashier.id}/change_password/',
            {'new_password': 'temp123'},
            format='json',
        )
        self.assertEqual(reuse.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            f'/api/accounts/users/{self.cashier.id}/change_password/',
            {'new_password': 'myownpass'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['must_change_password'])
        self.cashier_profile.refresh_from_db()
        self.assertFalse(self.cashier_profile.must_change_password)

        allowed = self.client.get('/api/accounts/users/')
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

    def test_admin_reset_sets_flag(self):
        self.cashier_profile.must_change_password = False
        self.cashier_profile.save()
        self._auth(self.admin)
        response = self.client.post(
            f'/api/accounts/users/{self.cashier.id}/change_password/',
            {'new_password': 'reset123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['must_change_password'])
        self.cashier_profile.refresh_from_db()
        self.assertTrue(self.cashier_profile.must_change_password)

    def test_admin_edit_password_sets_flag(self):
        self.cashier_profile.must_change_password = False
        self.cashier_profile.save()
        self._auth(self.admin)
        response = self.client.patch(
            f'/api/accounts/users/{self.cashier.id}/',
            {'password': 'another1'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cashier_profile.refresh_from_db()
        self.assertTrue(self.cashier_profile.must_change_password)
        self.cashier.refresh_from_db()
        self.assertTrue(self.cashier.check_password('another1'))
