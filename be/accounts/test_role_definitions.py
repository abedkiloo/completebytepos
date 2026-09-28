from django.test import TestCase

from accounts.models import Permission, Role
from accounts.role_definitions import (
    ROLE_DELIVERY_AGENT,
    ROLE_DISPATCHER,
    ROLE_FIELD_AGENT,
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

    def test_sync_default_roles_six_active_roles(self):
        ensure_permissions()
        roles = sync_default_roles()
        self.assertEqual(
            set(roles.keys()),
            {
                ROLE_SUPER_ADMIN,
                ROLE_MANAGER,
                ROLE_SALES,
                ROLE_FIELD_AGENT,
                ROLE_DISPATCHER,
                ROLE_DELIVERY_AGENT,
            },
        )
        super_admin = roles[ROLE_SUPER_ADMIN]
        self.assertGreater(super_admin.permissions.count(), 50)
        sales = roles[ROLE_SALES]
        self.assertFalse(sales.permissions.filter(module='users').exists())
        self.assertTrue(sales.permissions.filter(module='pos', action='create').exists())

    def test_legacy_roles_deactivated(self):
        Role.objects.create(name='Cashier', is_system_role=True, is_active=True)
        sync_default_roles()
        self.assertFalse(Role.objects.get(name='Cashier').is_active)

    def test_sync_default_roles_preserves_edited_permissions(self):
        ensure_permissions()
        sync_default_roles()
        sales = Role.objects.get(name=ROLE_SALES)
        inv_view = Permission.objects.get(module='invoicing', action='view')
        sales.permissions.add(inv_view)
        sync_default_roles()
        sales.refresh_from_db()
        self.assertTrue(sales.permissions.filter(module='invoicing', action='view').exists())

    def test_sync_adds_daily_notes_to_existing_sales_roles(self):
        ensure_permissions()
        sync_default_roles()
        sales = Role.objects.get(name=ROLE_SALES)
        sales.permissions.remove(
            *sales.permissions.filter(module='daily_notes')
        )
        self.assertFalse(sales.permissions.filter(module='daily_notes').exists())
        sync_default_roles()
        sales.refresh_from_db()
        self.assertTrue(sales.permissions.filter(module='daily_notes', action='view').exists())
        self.assertTrue(sales.permissions.filter(module='daily_notes', action='create').exists())

    def test_grant_daily_notes_to_custom_sales_role(self):
        ensure_permissions()
        role = Role.objects.create(name='Sales Person', is_system_role=False, is_active=True)
        role.permissions.add(Permission.objects.get(module='sales', action='view'))
        from accounts.role_definitions import grant_daily_notes_to_sales_roles
        grant_daily_notes_to_sales_roles()
        self.assertTrue(role.permissions.filter(module='daily_notes', action='view').exists())

    def test_grant_appraisals_to_custom_sales_role(self):
        ensure_permissions()
        role = Role.objects.create(name='Counter Sales', is_system_role=False, is_active=True)
        role.permissions.add(Permission.objects.get(module='sales', action='view'))
        from accounts.role_definitions import grant_appraisals_to_sales_roles
        grant_appraisals_to_sales_roles()
        self.assertTrue(role.permissions.filter(module='appraisals', action='view').exists())
        self.assertFalse(role.permissions.filter(module='appraisals', action='manage').exists())
