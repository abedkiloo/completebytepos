"""
Permission matrix alignment with the frontend route registry.

Keep MODULES_WITH_APP_ROUTES in sync with fe/src/utils/permissionRoutes.js
(PERMISSION_MODULE_ROUTES keys). Tests fail if a new UI module is added on one
side only.
"""

from django.test import TestCase

from accounts.role_definitions import PERMISSIONS_DATA, ensure_permissions

# Modules that unlock an app screen when granted to a custom/edited role (FE).
MODULES_WITH_APP_ROUTES = frozenset({
    'invoicing',
    'sales',
    'pos',
    'reports',
    'products',
    'categories',
    'inventory',
    'barcodes',
    'expenses',
    'income',
    'accounting',
    'daily_notes',
    'suppliers',
    'employees',
    'customers',
})


class PermissionMatrixTests(TestCase):
    def test_permissions_data_includes_all_ui_modules(self):
        """Every FE grantable module must exist in PERMISSIONS_DATA."""
        defined = {module for module, _action, _desc in PERMISSIONS_DATA}
        missing = MODULES_WITH_APP_ROUTES - defined
        self.assertEqual(
            missing,
            set(),
            f'Add PERMISSIONS_DATA rows for: {sorted(missing)}',
        )

    def test_ui_modules_have_at_least_view_action(self):
        ensure_permissions()
        from accounts.models import Permission

        for module in MODULES_WITH_APP_ROUTES:
            self.assertTrue(
                Permission.objects.filter(module=module, action='view').exists(),
                f'Missing {module}.view permission row',
            )
