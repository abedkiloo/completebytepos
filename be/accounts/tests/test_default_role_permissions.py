"""Default role permission matrix (maker-checker / financial separation)."""

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import (
    ROLE_FIELD_AGENT,
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
        cls.sales_role = Role.objects.get(name=ROLE_SALES)
        cls.field_role = Role.objects.get(name=ROLE_FIELD_AGENT)
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

    def test_debt_management_is_independently_grantable(self):
        self.assertTrue(self._has(self.manager_role, 'debt_management', 'view'))
        self.assertTrue(self._has(self.manager_role, 'debt_management', 'update'))
        self.assertTrue(self._has(self.manager_role, 'debt_management', 'approve'))
        self.assertTrue(self._has(self.sales_role, 'debt_management', 'view'))
        self.assertTrue(self._has(self.sales_role, 'debt_management', 'update'))
        self.assertFalse(self._has(self.sales_role, 'debt_management', 'approve'))

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

    def test_sales_role_lacks_approve_permissions(self):
        for module in ('products', 'inventory', 'settings', 'debt_management'):
            self.assertFalse(
                self._has(self.sales_role, module, 'approve'),
                f'Sales should not have {module}.approve',
            )

    def test_sales_role_has_catalog_create_import_only(self):
        self.assertTrue(self._has(self.sales_role, 'products', 'create'))
        self.assertTrue(self._has(self.sales_role, 'products', 'import'))
        self.assertFalse(self._has(self.sales_role, 'products', 'delete'))

    def test_manager_has_delivery_history(self):
        self.assertTrue(self._has(self.manager_role, 'delivery', 'history'))
        self.assertTrue(self._has(self.super_role, 'delivery', 'history'))
        self.assertFalse(self._has(self.sales_role, 'delivery', 'history'))

    def test_sales_role_can_do_delivery(self):
        self.assertTrue(self._has(self.sales_role, 'delivery', 'view'))
        self.assertTrue(self._has(self.sales_role, 'delivery', 'update'))
        self.assertTrue(self._has(self.field_role, 'delivery', 'view'))
        self.assertTrue(self._has(self.field_role, 'delivery', 'update'))

    def test_manager_lacks_users_roles_settings_modules(self):
        for module in ('users', 'roles', 'settings', 'modules'):
            self.assertFalse(
                self.manager_role.permissions.filter(module=module).exists(),
                f'Manager should not have {module} permissions',
            )

    def test_manager_lacks_delete_on_operational_modules(self):
        for module in ('products', 'inventory', 'sales', 'customers'):
            self.assertFalse(
                self._has(self.manager_role, module, 'delete'),
                f'Manager should not have {module}.delete',
            )

    def test_only_super_admin_has_settings_approve(self):
        self.assertTrue(self._has(self.super_role, 'settings', 'approve'))
        self.assertFalse(self._has(self.manager_role, 'settings', 'approve'))
        self.assertFalse(self._has(self.sales_role, 'settings', 'approve'))

    def test_manager_lacks_sale_rollback_and_accounting_correct(self):
        self.assertFalse(self._has(self.manager_role, 'sales', 'rollback'))
        self.assertFalse(self._has(self.manager_role, 'accounting', 'correct'))
        self.assertTrue(self._has(self.super_role, 'sales', 'rollback'))
        self.assertTrue(self._has(self.super_role, 'accounting', 'correct'))

    def test_ensure_permissions_creates_settings_approve_row(self):
        ensure_permissions()
        self.assertTrue(
            Permission.objects.filter(module='settings', action='approve').exists()
        )
