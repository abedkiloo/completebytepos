"""Unit tests for accounts.permissions factories and helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase
from rest_framework import status
from rest_framework.response import Response

from accounts.models import Permission, Role, UserProfile
from accounts.permissions import (
    CanViewAuditLog,
    HasModuleAccess,
    HasPermission,
    IsAdmin,
    IsManager,
    IsSuperAdmin,
    RequireAny,
    RequireModuleAccess,
    RequireModuleEnabled,
    RequirePerm,
    RequirePermPerAction,
    check_module_access,
    check_permission,
)
from accounts.role_definitions import ROLE_MANAGER, ensure_permissions, sync_default_roles
from settings.models import ModuleSettings


class _FakeView:
    action = 'list'


class PermissionsUnitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.factory = RequestFactory()
        cls.superuser = User.objects.create_superuser('perm_su', 'su@t.com', 'x')
        cls.staff = User.objects.create_user('perm_staff', password='x', is_staff=True)
        UserProfile.objects.create(user=cls.staff, role='admin', is_active=True)
        cls.manager = User.objects.create_user('perm_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
            is_active=True,
        )
        cls.bare = User.objects.create_user('perm_bare', password='x')
        # no profile

    def _req(self, user):
        request = self.factory.get('/')
        request.user = user
        return request

    def test_require_perm_superuser_bypass(self):
        klass = RequirePerm('sales', 'delete')
        self.assertTrue(klass().has_permission(self._req(self.superuser), _FakeView()))

    def test_require_perm_unauthenticated(self):
        klass = RequirePerm('sales', 'view')
        self.assertFalse(klass().has_permission(self._req(AnonymousUser()), _FakeView()))

    def test_require_perm_no_profile(self):
        klass = RequirePerm('sales', 'view')
        self.assertFalse(klass().has_permission(self._req(self.bare), _FakeView()))

    def test_require_perm_manager_has_sales_view(self):
        klass = RequirePerm('sales', 'view')
        self.assertTrue(klass().has_permission(self._req(self.manager), _FakeView()))

    def test_require_module_access(self):
        klass = RequireModuleAccess('sales')
        self.assertTrue(klass().has_permission(self._req(self.manager), _FakeView()))
        self.assertFalse(klass().has_permission(self._req(AnonymousUser()), _FakeView()))
        self.assertTrue(klass().has_permission(self._req(self.superuser), _FakeView()))
        self.assertFalse(klass().has_permission(self._req(self.bare), _FakeView()))

    def test_require_module_enabled(self):
        ModuleSettings.objects.update_or_create(
            module_name='suppliers',
            defaults={'description': 'Suppliers', 'is_enabled': False},
        )
        klass = RequireModuleEnabled('suppliers')
        self.assertFalse(klass().has_permission(self._req(self.manager), _FakeView()))
        ModuleSettings.objects.filter(module_name='suppliers').update(is_enabled=True)
        self.assertTrue(klass().has_permission(self._req(self.manager), _FakeView()))

    def test_require_perm_per_action_list_and_unknown(self):
        klass = RequirePermPerAction('sales')
        view = _FakeView()
        view.action = 'list'
        self.assertTrue(klass().has_permission(self._req(self.manager), view))
        view.action = 'custom_unknown'
        perm = klass()
        self.assertFalse(perm.has_permission(self._req(self.manager), view))
        self.assertIn('No permission rule', perm.message)

    def test_require_perm_per_action_with_default(self):
        klass = RequirePermPerAction('sales', default='view')
        view = _FakeView()
        view.action = 'weird'
        self.assertTrue(klass().has_permission(self._req(self.manager), view))

    def test_require_any_or_logic(self):
        with self.assertRaises(ValueError):
            RequireAny()
        klass = RequireAny(IsSuperAdmin, RequirePerm('sales', 'view'))
        self.assertTrue(klass().has_permission(self._req(self.manager), _FakeView()))
        self.assertFalse(klass().has_permission(self._req(self.bare), _FakeView()))

    def test_is_super_admin_is_admin_is_manager(self):
        self.assertTrue(IsSuperAdmin().has_permission(self._req(self.superuser), None))
        self.assertFalse(IsSuperAdmin().has_permission(self._req(self.manager), None))
        self.assertFalse(IsSuperAdmin().has_permission(self._req(AnonymousUser()), None))

        self.assertTrue(IsAdmin().has_permission(self._req(self.staff), None))
        self.assertFalse(IsAdmin().has_permission(self._req(self.manager), None))
        self.assertFalse(IsAdmin().has_permission(self._req(AnonymousUser()), None))

        self.assertTrue(IsManager().has_permission(self._req(self.manager), None))
        self.assertTrue(IsManager().has_permission(self._req(self.superuser), None))
        self.assertFalse(IsManager().has_permission(self._req(AnonymousUser()), None))
        self.assertFalse(IsManager().has_permission(self._req(self.bare), None))

    def test_can_view_audit_log(self):
        self.assertFalse(CanViewAuditLog().has_permission(self._req(AnonymousUser()), None))
        with patch('accounts.sensitive_edits.user_may_view_audit_log', return_value=True):
            self.assertTrue(CanViewAuditLog().has_permission(self._req(self.manager), None))

    def test_legacy_has_permission_and_module_access(self):
        self.assertTrue(
            HasPermission('sales', 'view').has_permission(self._req(self.manager), None)
        )
        self.assertTrue(
            HasModuleAccess('sales').has_permission(self._req(self.manager), None)
        )

    def test_check_permission_decorator(self):
        class View:
            @check_permission('sales', 'view')
            def ok(self, request):
                return Response({'ok': True})

            @check_permission('settings', 'approve')
            def deny(self, request):
                return Response({'ok': True})

        view = View()
        ok = view.ok(self._req(self.manager))
        self.assertEqual(ok.status_code, status.HTTP_200_OK)

        denied = view.deny(self._req(self.manager))
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        unauth = view.ok(self._req(AnonymousUser()))
        self.assertEqual(unauth.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_check_module_access_decorator(self):
        class View:
            @check_module_access('sales')
            def ok(self, request):
                return Response({'ok': True})

            @check_module_access('settings')
            def deny(self, request):
                return Response({'ok': True})

        view = View()
        self.assertEqual(view.ok(self._req(self.manager)).status_code, 200)
        self.assertEqual(view.deny(self._req(self.manager)).status_code, 403)
        self.assertEqual(view.ok(self._req(AnonymousUser())).status_code, 401)
