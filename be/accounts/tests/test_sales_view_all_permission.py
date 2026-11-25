"""Unit + module tests for the sales.view_all (view other staff sales) permission."""

from django.test import TestCase

from accounts.models import Permission
from accounts.role_definitions import (
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)


class SalesViewAllPermissionCatalogTests(TestCase):
    def test_ensure_permissions_creates_and_refreshes_view_all_description(self):
        ensure_permissions()
        perm = Permission.objects.get(module='sales', action='view_all')
        self.assertEqual(perm.name, 'sales.view_all')
        self.assertIn('other staff', perm.description.lower())

        perm.description = 'stale'
        perm.save(update_fields=['description'])
        ensure_permissions()
        perm.refresh_from_db()
        self.assertIn('other staff', perm.description.lower())

    def test_action_display_label_is_view_others_records(self):
        ensure_permissions()
        perm = Permission.objects.get(module='sales', action='view_all')
        self.assertEqual(perm.get_action_display(), "View others' records")

    def test_sales_module_pack_leaves_view_all_opt_in(self):
        ensure_permissions()
        roles = sync_default_roles()
        sales = roles[ROLE_SALES]
        self.assertFalse(
            sales.permissions.filter(module='sales', action='view_all').exists()
        )
