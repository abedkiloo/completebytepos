"""
P2 maker-checker: store settings, payment methods, receipt legal, module toggles, role permissions.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import ROLE_SUPER_ADMIN, sync_default_roles
from approvals.models import PendingChange
from approvals.registry import (
    ACTION_PAYMENT_METHODS,
    ACTION_RECEIPT_LEGAL,
    ACTION_ROLE_PERMISSIONS,
    ACTION_STORE_SETTINGS,
)
from approvals.tests.test_maker_checker import _enable_maker_checker
from settings.models import StoreSettings
from settings.settings_service import SettingsService
from utils.tests.api_test_base import SuperAdminAPITestCase


def setUpModule():
    _enable_maker_checker(enabled=True)


def tearDownModule():
    _enable_maker_checker(enabled=True)
    SettingsService.set('products', 'show_status', True)
    SettingsService.invalidate('products')


class MakerCheckerP2TestMixin:
    def tearDown(self):
        _enable_maker_checker(enabled=True)
        SettingsService.set('products', 'show_status', True)
        SettingsService.invalidate('products')
        super().tearDown()


class MakerCheckerStoreSettingsTests(MakerCheckerP2TestMixin, SuperAdminAPITestCase):
    url = '/api/settings/store-settings/'

    def setUp(self):
        super().setUp()
        _enable_maker_checker(enabled=True)
        PendingChange.objects.all().delete()

    def tearDown(self):
        _enable_maker_checker(enabled=True)
        super().tearDown()

    def _checker_client(self):
        checker = User.objects.create_user('p2_chk', password='x', is_staff=True)
        UserProfile.objects.create(
            user=checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def test_payment_methods_pending_until_approved(self):
        store = StoreSettings.load()
        original = list(store.enabled_payment_methods)
        resp = self.client.patch(
            self.url,
            {
                'enabled_payment_methods': ['cash', 'mpesa'],
                'reason': 'Add M-Pesa for rural stores',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        store.refresh_from_db()
        self.assertEqual(store.enabled_payment_methods, original)
        pending = PendingChange.objects.get(action_type=ACTION_PAYMENT_METHODS)
        approve = self._checker_client().post(
            f'/api/approvals/pending-changes/{pending.id}/approve/',
            {},
            format='json',
        )
        self.assertEqual(approve.status_code, status.HTTP_200_OK)
        store.refresh_from_db()
        self.assertEqual(store.enabled_payment_methods, ['cash', 'mpesa'])

    def test_receipt_footer_pending_until_approved(self):
        resp = self.client.patch(
            self.url,
            {
                'receipt_footer_text': 'Licensed retailer — VAT reg 123',
                'reason': 'Legal footer update',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        pending = PendingChange.objects.get(action_type=ACTION_RECEIPT_LEGAL)
        self._checker_client().post(
            f'/api/approvals/pending-changes/{pending.id}/approve/',
            {},
            format='json',
        )
        store = StoreSettings.load()
        self.assertEqual(store.receipt_footer_text, 'Licensed retailer — VAT reg 123')

    def test_maker_checker_toggle_applies_immediately(self):
        try:
            resp = self.client.patch(
                self.url,
                {'maker_checker_enabled': False},
                format='json',
            )
            self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
            self.assertFalse(StoreSettings.load().maker_checker_enabled)
        finally:
            _enable_maker_checker(enabled=True)
            self.assertTrue(StoreSettings.load().maker_checker_enabled)


class MakerCheckerModuleSettingsTests(MakerCheckerP2TestMixin, SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        _enable_maker_checker(enabled=True)
        PendingChange.objects.all().delete()
        SettingsService.invalidate('products')

    def _checker_client(self):
        checker = User.objects.create_user('p2_mod_chk', password='x', is_staff=True)
        UserProfile.objects.create(
            user=checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def test_module_toggle_pending_until_approved(self):
        before = SettingsService.get('products', 'show_status')
        resp = self.client.patch(
            '/api/settings/products/',
            {'show_status': not before, 'reason': 'Hide status chips in catalog'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.assertEqual(SettingsService.get('products', 'show_status'), before)
        pending = PendingChange.objects.get(
            entity_type='settings.ModuleSetting',
            action_type=ACTION_STORE_SETTINGS,
        )
        self._checker_client().post(
            f'/api/approvals/pending-changes/{pending.id}/approve/',
            {},
            format='json',
        )
        SettingsService.invalidate('products')
        self.assertEqual(SettingsService.get('products', 'show_status'), not before)


class MakerCheckerRolePermissionsTests(MakerCheckerP2TestMixin, SuperAdminAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_default_roles()
        cls.role = Role.objects.create(
            name='MC Test Role',
            description='P2 permissions',
            is_active=True,
        )
        cls.perm_a = Permission.objects.filter(module='products').first()
        cls.perm_b = Permission.objects.filter(module='sales').first()

    def setUp(self):
        super().setUp()
        _enable_maker_checker(enabled=True)
        PendingChange.objects.all().delete()
        self.role.permissions.clear()

    def _checker_client(self):
        checker = User.objects.create_user('p2_role_chk', password='x', is_staff=True)
        UserProfile.objects.create(
            user=checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def test_role_permission_assign_pending_until_approved(self):
        self.assertEqual(self.role.permissions.count(), 0)
        resp = self.client.put(
            f'/api/accounts/roles/{self.role.id}/',
            {
                'name': self.role.name,
                'description': self.role.description,
                'is_active': True,
                'permission_ids': [self.perm_a.id, self.perm_b.id],
                'reason': 'Grant catalog + sales for pilot',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.assertEqual(self.role.permissions.count(), 0)
        pending = PendingChange.objects.get(action_type=ACTION_ROLE_PERMISSIONS)
        self._checker_client().post(
            f'/api/approvals/pending-changes/{pending.id}/approve/',
            {},
            format='json',
        )
        self.role.refresh_from_db()
        self.assertEqual(self.role.permissions.count(), 2)
