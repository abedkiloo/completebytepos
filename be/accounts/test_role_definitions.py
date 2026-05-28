from django.test import TestCase

from accounts.models import Permission, Role
from accounts.role_definitions import (
    ROLE_MANAGER,
    ROLE_SALES,
    ROLE_SUPER_ADMIN,
    ensure_permissions,
    sync_default_roles,
)


class RoleDefinitionsTestCase(TestCase):
    def test_ensure_permissions_creates_matrix(self):
        created = ensure_permissions()
        self.assertGreaterEqual(created, 1)
        self.assertTrue(Permission.objects.filter(module='pos', action='view').exists())

    def test_sync_default_roles_three_active_roles(self):
        ensure_permissions()
        roles = sync_default_roles()
        self.assertEqual(set(roles.keys()), {ROLE_SUPER_ADMIN, ROLE_MANAGER, ROLE_SALES})
        super_admin = roles[ROLE_SUPER_ADMIN]
        self.assertGreater(super_admin.permissions.count(), 50)
        sales = roles[ROLE_SALES]
        self.assertFalse(sales.permissions.filter(module='users').exists())
        self.assertTrue(sales.permissions.filter(module='pos', action='create').exists())

    def test_legacy_roles_deactivated(self):
        Role.objects.create(name='Cashier', is_system_role=True, is_active=True)
        sync_default_roles()
        self.assertFalse(Role.objects.get(name='Cashier').is_active)
