"""
Single source of truth for bootstrap roles, users, and permission matrices.

Used by ``init_permissions`` and ``create_users`` management commands.
"""

from typing import Optional

from accounts.models import Permission, Role

ROLE_SUPER_ADMIN = 'Super Admin'
ROLE_MANAGER = 'Manager'
ROLE_SALES = 'Sales Personnel'

# Legacy names kept for migrations / existing DB rows; not created on fresh install.
LEGACY_ROLE_NAMES = ('Admin', 'Administrator', 'Cashier')

PERMISSIONS_DATA = [
    ('products', 'view', 'View products'),
    ('products', 'create', 'Create products'),
    ('products', 'update', 'Update products'),
    ('products', 'delete', 'Delete products'),
    ('products', 'export', 'Export products'),
    ('products', 'import', 'Import products'),
    ('categories', 'view', 'View categories'),
    ('categories', 'create', 'Create categories'),
    ('categories', 'update', 'Update categories'),
    ('categories', 'delete', 'Delete categories'),
    ('suppliers', 'view', 'View suppliers'),
    ('suppliers', 'create', 'Create suppliers'),
    ('suppliers', 'update', 'Update suppliers'),
    ('suppliers', 'delete', 'Delete suppliers'),
    ('suppliers', 'export', 'Export suppliers'),
    ('suppliers', 'manage', 'Manage suppliers'),
    ('inventory', 'view', 'View inventory'),
    ('inventory', 'create', 'Create inventory movements'),
    ('inventory', 'update', 'Update inventory'),
    ('inventory', 'delete', 'Delete inventory movements'),
    ('inventory', 'manage', 'Manage inventory settings'),
    ('sales', 'view', 'View sales'),
    ('sales', 'create', 'Create sales'),
    ('sales', 'update', 'Update sales'),
    ('sales', 'delete', 'Delete sales'),
    ('sales', 'export', 'Export sales'),
    ('pos', 'view', 'Access POS'),
    ('pos', 'create', 'Create sales via POS'),
    ('barcodes', 'view', 'View barcodes'),
    ('barcodes', 'create', 'Generate barcodes'),
    ('barcodes', 'export', 'Export barcodes'),
    ('reports', 'view', 'View reports'),
    ('reports', 'export', 'Export reports'),
    ('customers', 'view', 'View customers'),
    ('customers', 'create', 'Create customers'),
    ('customers', 'update', 'Update customers'),
    ('customers', 'delete', 'Delete customers'),
    ('customers', 'export', 'Export customers'),
    ('invoicing', 'view', 'View invoices and payments'),
    ('invoicing', 'create', 'Create invoices and record payments'),
    ('invoicing', 'update', 'Update invoices'),
    ('invoicing', 'approve', 'Approve / send invoices'),
    ('invoicing', 'export', 'Export invoices'),
    ('expenses', 'view', 'View expenses'),
    ('expenses', 'create', 'Create expenses'),
    ('expenses', 'update', 'Update expenses'),
    ('expenses', 'delete', 'Delete expenses'),
    ('expenses', 'approve', 'Approve expenses'),
    ('expenses', 'export', 'Export expenses'),
    ('income', 'view', 'View income'),
    ('income', 'create', 'Create income'),
    ('income', 'update', 'Update income'),
    ('income', 'delete', 'Delete income'),
    ('income', 'approve', 'Approve income'),
    ('income', 'export', 'Export income'),
    ('bank_accounts', 'view', 'View bank accounts'),
    ('bank_accounts', 'create', 'Create bank accounts'),
    ('bank_accounts', 'update', 'Update bank accounts'),
    ('bank_accounts', 'delete', 'Delete bank accounts'),
    ('bank_accounts', 'manage', 'Manage bank accounts'),
    ('money_transfer', 'view', 'View money transfers'),
    ('money_transfer', 'create', 'Create money transfers'),
    ('money_transfer', 'approve', 'Approve money transfers'),
    ('accounting', 'view', 'View accounting'),
    ('accounting', 'create', 'Create journal entries'),
    ('accounting', 'update', 'Update accounting'),
    ('accounting', 'export', 'Export accounting reports'),
    ('users', 'view', 'View users'),
    ('users', 'create', 'Create users'),
    ('users', 'update', 'Update users'),
    ('users', 'delete', 'Delete users'),
    ('users', 'manage', 'Manage users'),
    ('roles', 'view', 'View roles'),
    ('roles', 'create', 'Create roles'),
    ('roles', 'update', 'Update roles'),
    ('roles', 'delete', 'Delete roles'),
    ('roles', 'manage', 'Manage roles'),
    ('settings', 'view', 'View settings'),
    ('settings', 'update', 'Update settings'),
    ('settings', 'manage', 'Manage settings'),
    ('modules', 'view', 'View module settings'),
    ('modules', 'update', 'Update module settings'),
    ('modules', 'manage', 'Manage module settings'),
]

# profile_role maps to UserProfile.role (legacy enum).
BOOTSTRAP_USERS = [
    {
        'username': 'admin',
        'password': 'admin123',
        'email': 'admin@example.com',
        'profile_role': 'super_admin',
        'custom_role_name': ROLE_SUPER_ADMIN,
        'is_superuser': True,
        'is_staff': True,
        'label': 'Super Admin',
    },
    {
        'username': 'manager',
        'password': 'manager123',
        'email': 'manager@example.com',
        'profile_role': 'manager',
        'custom_role_name': ROLE_MANAGER,
        'is_superuser': False,
        'is_staff': True,
        'label': 'Manager',
    },
    {
        'username': 'sales',
        'password': 'sales123',
        'email': 'sales@example.com',
        'profile_role': 'cashier',
        'custom_role_name': ROLE_SALES,
        'is_superuser': False,
        'is_staff': False,
        'label': 'Sales Personnel',
    },
]

DEMO_PRODUCTS = [
    {
        'name': 'Bottled Water 500ml',
        'sku': 'DEMO-WATER-500',
        'barcode': '8901000000001',
        'mrp': '50.00',
        'price': '40.00',
        'cost': '25.00',
        'stock': 100,
        'unit': 'bottle',
    },
    {
        'name': 'Bread Loaf White',
        'sku': 'DEMO-BREAD-WHT',
        'barcode': '8901000000002',
        'mrp': '80.00',
        'price': '70.00',
        'cost': '45.00',
        'stock': 50,
        'unit': 'piece',
    },
    {
        'name': 'Cooking Oil 1L',
        'sku': 'DEMO-OIL-1L',
        'barcode': '8901000000003',
        'mrp': '350.00',
        'price': '320.00',
        'cost': '260.00',
        'stock': 30,
        'unit': 'bottle',
    },
]

# Screens each role should use day-to-day (documentation + FE hints).
ROLE_SCREEN_MATRIX = {
    ROLE_SUPER_ADMIN: [
        'Dashboard (full KPIs)',
        'Module Settings',
        'Users & Roles',
        'Products / Categories / Inventory',
        'POS + Billing',
        'Reports hub',
        'Accounting / Expenses / Income',
        'System settings',
    ],
    ROLE_MANAGER: [
        'Dashboard (operations KPIs)',
        'Products / Categories / Inventory',
        'Stock purchase & transfers',
        'POS + Billing',
        'Customers',
        'Reports (sales, stock, P&L)',
        'Expenses / Income (no user admin)',
    ],
    ROLE_SALES: [
        'Dashboard (today sales + quick POS)',
        'POS (/pos)',
        'Billing POS (/pos/billing)',
        'Customers (add walk-in / credit)',
        'Product lookup (view only)',
    ],
}


def ensure_permissions():
    """Create missing Permission rows; return count created."""
    created = 0
    for module, action, description in PERMISSIONS_DATA:
        _, was_created = Permission.objects.get_or_create(
            module=module,
            action=action,
            defaults={
                'name': f'{module}.{action}',
                'description': description,
            },
        )
        if was_created:
            created += 1
    return created


def _manager_queryset():
    return Permission.objects.filter(
        module__in=[
            'products', 'categories', 'suppliers', 'inventory',
            'sales', 'pos', 'barcodes', 'reports', 'expenses',
            'income', 'customers', 'invoicing', 'bank_accounts',
            'money_transfer', 'accounting',
        ],
    ).exclude(action='delete')


def _sales_queryset():
    return Permission.objects.filter(
        module__in=[
            'products', 'categories', 'sales', 'pos', 'barcodes',
            'customers', 'invoicing',
        ],
        action__in=['view', 'create'],
    )


def sync_default_roles(created_by=None):
    """
    Upsert the three system roles and refresh their permission sets every run.
    """
    all_perms = Permission.objects.all()

    super_admin, _ = Role.objects.update_or_create(
        name=ROLE_SUPER_ADMIN,
        defaults={
            'description': 'Full system access — configuration, users, modules, all data',
            'is_system_role': True,
            'is_active': True,
            'created_by': created_by,
        },
    )
    super_admin.permissions.set(all_perms)

    manager, _ = Role.objects.update_or_create(
        name=ROLE_MANAGER,
        defaults={
            'description': 'Store operations — inventory, reports, finance (no user/role admin)',
            'is_system_role': True,
            'is_active': True,
            'created_by': created_by,
        },
    )
    manager.permissions.set(_manager_queryset())

    sales, _ = Role.objects.update_or_create(
        name=ROLE_SALES,
        defaults={
            'description': 'Front-line sales — POS, billing, customers; view products only',
            'is_system_role': True,
            'is_active': True,
            'created_by': created_by,
        },
    )
    sales.permissions.set(_sales_queryset())

    # Deactivate legacy duplicate roles so the UI shows a clean trio.
    Role.objects.filter(name__in=LEGACY_ROLE_NAMES).update(is_active=False)

    return {
        ROLE_SUPER_ADMIN: super_admin,
        ROLE_MANAGER: manager,
        ROLE_SALES: sales,
    }


def get_role_by_name(name: str) -> Optional[Role]:
    return Role.objects.filter(name=name, is_active=True).first()
