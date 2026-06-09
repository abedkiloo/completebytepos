"""Custom role permissions: auth/me, API gates, and sync preservation."""

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import (
    ROLE_MANAGER,
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from settings.models import ModuleSettings


def _enable_module(name):
    ModuleSettings.objects.update_or_create(
        module_name=name,
        defaults={'description': name, 'is_enabled': True},
    )


class CustomRolePermissionTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.sales_role = Role.objects.get(name=ROLE_SALES)
        cls.manager_role = Role.objects.get(name=ROLE_MANAGER)

        cls.sales_user = User.objects.create_user('sales_custom', password='sales123')
        UserProfile.objects.create(
            user=cls.sales_user,
            role='cashier',
            custom_role=cls.sales_role,
            is_active=True,
        )

    def _auth(self, user):
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def _perm(self, module, action):
        return Permission.objects.get(module=module, action=action)

    def test_sync_preserves_edited_sales_role_permissions(self):
        self.sales_role.permissions.add(self._perm('invoicing', 'view'))
        sync_default_roles()
        self.sales_role.refresh_from_db()
        self.assertTrue(self.sales_role.has_permission('invoicing', 'view'))

    def test_sync_preserves_edited_manager_role_permissions(self):
        self.manager_role.permissions.add(self._perm('invoicing', 'approve'))
        sync_default_roles()
        self.manager_role.refresh_from_db()
        self.assertTrue(self.manager_role.has_permission('invoicing', 'approve'))

    def test_profile_has_permission_reflects_role_edit(self):
        self.sales_role.permissions.add(
            self._perm('invoicing', 'view'),
            self._perm('invoicing', 'create'),
        )
        profile = self.sales_user.profile
        self.assertTrue(profile.has_permission('invoicing', 'view'))
        self.assertTrue(profile.has_permission('invoicing', 'create'))
        self.assertFalse(profile.has_permission('reports', 'view'))

    def test_auth_me_returns_permissions_after_role_edit(self):
        self.sales_role.permissions.add(
            self._perm('invoicing', 'view'),
            self._perm('invoicing', 'create'),
        )
        self._auth(self.sales_user)
        response = self.client.get('/api/accounts/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {p['name'] for p in response.data['permissions']}
        self.assertIn('invoicing.view', names)
        self.assertIn('invoicing.create', names)
        self.assertNotIn('reports.view', names)

    def test_get_all_permissions_matches_role_after_edit(self):
        self.sales_role.permissions.add(self._perm('reports', 'view'))
        perms = list(self.sales_user.profile.get_all_permissions())
        self.assertTrue(any(p.module == 'reports' and p.action == 'view' for p in perms))

    def test_sales_with_invoicing_view_can_list_invoices(self):
        _enable_module('invoicing')
        self.sales_role.permissions.add(
            self._perm('invoicing', 'view'),
            self._perm('invoicing', 'create'),
        )
        self._auth(self.sales_user)
        response = self.client.get('/api/sales/invoices/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sales_without_invoicing_view_cannot_list_invoices(self):
        _enable_module('invoicing')
        invoicing_perms = Permission.objects.filter(module='invoicing')
        self.sales_role.permissions.remove(*invoicing_perms)
        self._auth(self.sales_user)
        response = self.client.get('/api/sales/invoices/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_with_reports_view_can_open_reports_dashboard(self):
        _enable_module('reports')
        self.sales_role.permissions.add(self._perm('reports', 'view'))
        self._auth(self.sales_user)
        response = self.client.get('/api/reports/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sales_without_reports_view_cannot_open_reports_dashboard(self):
        _enable_module('reports')
        report_perms = list(Permission.objects.filter(module='reports'))
        self.sales_role.permissions.remove(*report_perms)
        self._auth(self.sales_user)
        response = self.client.get('/api/reports/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_new_permission_module_does_not_break_has_permission(self):
        """Future modules: ensure_permissions + role grant works end-to-end."""
        perm, _ = Permission.objects.get_or_create(
            module='future_module',
            action='view',
            defaults={'name': 'future_module.view', 'description': 'Future'},
        )
        self.sales_role.permissions.add(perm)
        self.assertTrue(self.sales_user.profile.has_permission('future_module', 'view'))
