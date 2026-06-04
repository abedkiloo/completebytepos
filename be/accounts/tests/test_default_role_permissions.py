"""Default role permission matrix (maker-checker / financial separation)."""

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import (
    ROLE_MANAGER,
    ROLE_SALES,
    ROLE_SUPER_ADMIN,
    ensure_permissions,
    sync_default_roles,
)


class DefaultRolePermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.manager_role = Role.objects.get(name=ROLE_MANAGER)
        cls.super_role = Role.objects.get(name=ROLE_SUPER_ADMIN)

    def _has(self, role, module, action):
        return role.permissions.filter(module=module, action=action).exists()

    def test_manager_cannot_approve_major_financial_modules(self):
        for module in ('expenses', 'income', 'money_transfer', 'invoicing'):
            self.assertFalse(
                self._has(self.manager_role, module, 'approve'),
                f'Manager should not have {module}.approve by default',
            )

    def test_manager_can_approve_catalog_and_stock(self):
        self.assertTrue(self._has(self.manager_role, 'products', 'approve'))
        self.assertTrue(self._has(self.manager_role, 'inventory', 'approve'))

    def test_manager_can_create_expenses(self):
        self.assertTrue(self._has(self.manager_role, 'expenses', 'create'))
        self.assertTrue(self._has(self.manager_role, 'expenses', 'view'))

    def test_super_admin_has_all_permissions(self):
        total = Permission.objects.count()
        self.assertEqual(self.super_role.permissions.count(), total)

    def test_profile_has_permission_reflects_role(self):
        user = User.objects.create_user('mgr_perm', password='x')
        UserProfile.objects.create(
            user=user,
            role='manager',
            custom_role=self.manager_role,
        )
        self.assertFalse(user.profile.has_permission('expenses', 'approve'))
        self.assertTrue(user.profile.has_permission('expenses', 'create'))
        self.assertTrue(user.profile.has_permission('products', 'approve'))
