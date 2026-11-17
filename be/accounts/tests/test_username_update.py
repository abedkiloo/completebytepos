"""Login name can be changed, and it stays unique."""

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import AuditLog, UserProfile
from accounts.user_write import normalize_username, prepare_user_write_data, username_change_audit
from settings.settings_service import SettingsService
from utils.tests.api_test_base import SalesAPITestCase, SuperAdminAPITestCase


class NormalizeUsernameUnitTests(SimpleTestCase):
    def test_rejects_blank_and_overlong_names(self):
        for value in ('', '   ', None, 12, 'a' * 151):
            with self.assertRaises(ValidationError):
                normalize_username(value)

    def test_rejects_spaces_and_other_characters(self):
        with self.assertRaises(ValidationError):
            normalize_username('jane wambua')

    def test_audit_records_the_old_name_only_when_it_changes(self):
        class Stub:
            username = 'jane.wambua'

        changed = username_change_audit('cashier1', Stub(), {'username': 'jane.wambua'}, self_service=False)
        self.assertEqual(changed['previous_username'], 'cashier1')
        self.assertEqual(changed['username'], 'jane.wambua')
        self.assertNotIn('email', changed)

        same = username_change_audit('jane.wambua', Stub(), {'first_name': 'Jane'}, self_service=True)
        self.assertNotIn('previous_username', same)
        self.assertTrue(same['self_service'])

    def test_prepare_strips_username(self):
        payload, _profile = prepare_user_write_data({'username': '  jane.wambua  '})
        self.assertEqual(payload['username'], 'jane.wambua')


class NormalizeUsernameDbTests(TestCase):
    def test_allows_the_same_user_and_rejects_a_taken_name(self):
        owner = User.objects.create_user(username='owner_name', password='pass1234')
        User.objects.create_user(username='taken_name', password='pass1234')
        self.assertEqual(
            normalize_username('owner_name', exclude_user_id=owner.id),
            'owner_name',
        )
        with self.assertRaises(ValidationError) as caught:
            normalize_username('taken_name', exclude_user_id=owner.id)
        self.assertNotIn('email', str(caught.exception))

    def test_stress_many_distinct_names(self):
        for index in range(200):
            name = f'load{index}'
            self.assertEqual(normalize_username(name), name)


class UsernameUpdateAPITests(SuperAdminAPITestCase):
    def test_admin_can_change_a_username(self):
        target = User.objects.create_user(
            username='old_login',
            email='old@example.com',
            password='pass1234',
        )
        response = self.client.patch(
            f'/api/accounts/users/{target.id}/',
            {'username': '  new.login  '},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'new.login')
        target.refresh_from_db()
        self.assertEqual(target.username, 'new.login')
        self.assertTrue(target.check_password('pass1234'))
        audit = AuditLog.objects.filter(object_id=str(target.id)).latest('id')
        self.assertEqual(audit.changes.get('previous_username'), 'old_login')
        self.assertEqual(audit.changes.get('username'), 'new.login')

    def test_keeping_the_same_username_still_saves(self):
        target = User.objects.create_user(username='same_login', password='pass1234')
        response = self.client.patch(
            f'/api/accounts/users/{target.id}/',
            {'username': 'same_login', 'first_name': 'Same'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        target.refresh_from_db()
        self.assertEqual(target.username, 'same_login')
        self.assertEqual(target.first_name, 'Same')

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user(username='already_used', password='pass1234', email='hidden-other@example.com')
        target = User.objects.create_user(username='still_mine', password='pass1234')
        response = self.client.patch(
            f'/api/accounts/users/{target.id}/',
            {'username': 'already_used'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        body = str(response.data)
        self.assertNotIn('hidden-other@example.com', body)
        target.refresh_from_db()
        self.assertEqual(target.username, 'still_mine')

    def test_username_edit_is_off_with_the_user_edit_setting(self):
        target = User.objects.create_user(username='gated_login', password='pass1234')
        SettingsService.set('users', 'enable_user_edit', False)
        response = self.client.patch(
            f'/api/accounts/users/{target.id}/',
            {'username': 'should_not_save'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        target.refresh_from_db()
        self.assertEqual(target.username, 'gated_login')
        SettingsService.set('users', 'enable_user_edit', True)
        response = self.client.patch(
            f'/api/accounts/users/{target.id}/',
            {'username': 'now_saved'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        target.refresh_from_db()
        self.assertEqual(target.username, 'now_saved')


class UsernameUpdateSecurityTests(SalesAPITestCase):
    def test_unauthenticated_update_is_rejected(self):
        target = User.objects.create_user(username='locked_login', password='pass1234')
        client = APIClient()
        response = client.patch(
            f'/api/accounts/users/{target.id}/',
            {'username': 'stolen'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        target.refresh_from_db()
        self.assertEqual(target.username, 'locked_login')

    def test_sales_cannot_rename_someone_else(self):
        other = User.objects.create_user(
            username='other_login',
            email='other-secret@example.com',
            password='pass1234',
        )
        UserProfile.objects.create(user=other, role='cashier', phone_number='254718515142')
        response = self.client.patch(
            f'/api/accounts/users/{other.id}/',
            {'username': 'hijack'},
            format='json',
        )
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
        body = str(response.data)
        self.assertNotIn('other-secret@example.com', body)
        self.assertNotIn('254718515142', body)
        self.assertNotIn('0718515142', body)
        other.refresh_from_db()
        self.assertEqual(other.username, 'other_login')
        self.assertFalse(other.is_staff)

    def test_sales_can_rename_themselves_without_becoming_staff(self):
        response = self.client.patch(
            f'/api/accounts/users/{self.sales_user.id}/',
            {'username': 'sales.renamed', 'is_staff': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.sales_user.refresh_from_db()
        self.assertEqual(self.sales_user.username, 'sales.renamed')
        self.assertFalse(self.sales_user.is_staff)
