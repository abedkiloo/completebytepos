"""
Single source of truth for bootstrap roles, users, and permission matrices.

Used by ``init_permissions`` and ``create_users`` management commands.
"""

from typing import Optional

from accounts.models import Permission, Role

ROLE_SUPER_ADMIN = 'Super Admin'
ROLE_MANAGER = 'Manager'
ROLE_SALES = 'Sales Personnel'
ROLE_FIELD_AGENT = 'Field Sales'  # was Field Agent
ROLE_DISPATCHER = 'Dispatcher'
ROLE_DELIVERY_AGENT = 'Delivery Driver'  # was Delivery Agent

# Legacy names kept for migrations / existing DB rows; not created on fresh install.
LEGACY_ROLE_NAMES = ('Admin', 'Administrator', 'Cashier')

# When adding modules with UI routes, also update fe/src/utils/permissionRoutes.js
# (PERMISSION_MODULE_ROUTES) and be/accounts/tests/test_permission_matrix.py.
PERMISSIONS_DATA = [
    ('products', 'view', 'View products'),
    ('products', 'create', 'Create products'),
    ('products', 'update', 'Update products'),
    ('products', 'delete', 'Delete products'),
    ('products', 'approve', 'Approve product / price changes'),
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
    ('employees', 'view', 'View employees'),
    ('employees', 'create', 'Create employees'),
    ('employees', 'update', 'Update employees'),
    ('employees', 'delete', 'Delete employees'),
    ('employees', 'export', 'Export employees'),
    ('employees', 'manage', 'Manage employees'),
    ('inventory', 'view', 'View inventory'),
    ('inventory', 'create', 'Create inventory movements'),
    ('inventory', 'update', 'Update inventory'),
    ('inventory', 'delete', 'Delete inventory movements'),
    ('inventory', 'manage', 'Manage inventory settings'),
    ('inventory', 'approve', 'Approve stock adjustments and transfers'),
    ('sales', 'view', 'View sales'),
    ('sales', 'create', 'Create sales'),
    ('sales', 'update', 'Update sales'),
    ('sales', 'delete', 'Delete sales'),
    ('sales', 'refund', 'Refund completed sales'),
    ('sales', 'export', 'Export sales'),
    ('sales', 'daily_sales', 'View daily sales tracker (paid vs debt by day)'),
    ('agents', 'view', 'View customer sites and visit media'),
    ('agents', 'create', 'Create customer sites and media'),
    ('agents', 'update', 'Update sites, upload media, finalize visits'),
    ('dispatch', 'view', 'View field-order dispatch queue'),
    ('dispatch', 'update', 'Pack and assign field orders'),
    ('delivery', 'view', 'View delivery routes and stops'),
    ('delivery', 'update', 'Arrive, deliver, collect, POD, complete stops'),
    ('payments', 'view', 'View payment intents'),
    ('payments', 'create', 'Create payment intents and send STK'),
    ('messaging', 'view', 'View message outbox'),
    ('messaging', 'create', 'Queue SMS receipts and reminders'),
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
    ('settings', 'approve', 'Approve store settings and maker-checker queue'),
    ('modules', 'view', 'View module settings'),
    ('modules', 'update', 'Update module settings'),
    ('modules', 'manage', 'Manage module settings'),
    ('daily_notes', 'view', 'View daily notes'),
    ('daily_notes', 'create', 'Create daily notes'),
    ('daily_notes', 'update', 'Update daily notes'),
    ('daily_notes', 'delete', 'Delete daily notes'),
    ('daily_notes', 'view_all', 'View all staff daily notes'),
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

# Screens each role should use day-to-day (documentation + FE hints).
ROLE_SCREEN_MATRIX = {
    ROLE_SUPER_ADMIN: [
        'Dashboard (full KPIs)',
        'Module Settings',
        'Users & Roles',
        'Products / Categories / Inventory',
        'POS + Terminal POS',
        'Daily Sales Tracker',
        'Reports hub',
        'Accounting / Expenses / Income',
        'System settings',
    ],
    ROLE_MANAGER: [
        'Dashboard (operations KPIs)',
        'Products / Categories / Inventory',
        'Stock purchase & transfers',
        'POS + Terminal POS',
        'Customers',
        'Reports (sales, stock, P&L)',
        'Expenses / Income (no user admin)',
    ],
    ROLE_SALES: [
        'Dashboard (today sales + quick POS)',
        'POS (/pos)',
        'Terminal POS (/pos/billing)',
        'Customers (add walk-in / credit)',
        'Products & categories (add / import — manager sets prices)',
    ],
    ROLE_FIELD_AGENT: [
        'Visit orders (customer → products → pin → place)',
        'POS / sales (same as Sales)',
        'Customers (lookup / create)',
    ],
    ROLE_DISPATCHER: [
        'Dispatch queue (submitted / packing / ready)',
        'Pack field orders (allocate-on-pack)',
        'Assign delivery driver',
    ],
    ROLE_DELIVERY_AGENT: [
        'Today’s route (ordered stops)',
        'Map-first stop delivery + POD',
        'Collect cash / mark debt',
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


# Managers operate day-to-day but must not approve major financial records by default.
_MANAGER_NO_APPROVE_MODULES = frozenset({
    'expenses',
    'income',
    'money_transfer',
    'invoicing',
})


def _manager_queryset():
    return (
        Permission.objects.filter(
            module__in=[
                'products', 'categories', 'suppliers', 'inventory',
                'sales', 'pos', 'barcodes', 'reports', 'expenses',
                'income', 'customers', 'invoicing', 'bank_accounts',
                'money_transfer', 'accounting', 'daily_notes', 'dispatch',
                'delivery', 'payments', 'messaging',
            ],
        )
        .exclude(action='delete')
        .exclude(
            action='approve',
            module__in=_MANAGER_NO_APPROVE_MODULES,
        )
        # Daily Sales Tracker is admin-grantable; not in default manager pack.
        .exclude(module='sales', action='daily_sales')
    )


def _sales_queryset():
    return Permission.objects.filter(
        module__in=[
            'products', 'categories', 'sales', 'pos', 'barcodes',
            'customers', 'invoicing', 'daily_notes', 'payments',
        ],
        action__in=['view', 'create', 'update', 'import'],
    ) | Permission.objects.filter(
        module='messaging', action__in=['view', 'create'],
    )


def _field_agent_queryset():
    """Field Sales permission pack — sales + customers (visit orders are normal sales)."""
    return (
        _sales_queryset()
        | Permission.objects.filter(
            module='agents',
            action__in=['view', 'create', 'update'],
        )
    )


def _dispatcher_queryset():
    return Permission.objects.filter(
        module='dispatch',
        action__in=['view', 'update'],
    )


def _delivery_agent_queryset():
    return (
        Permission.objects.filter(
            module='delivery',
            action__in=['view', 'update'],
        )
        | Permission.objects.filter(
            module='payments',
            action__in=['view', 'create'],
        )
    )


def _rename_role(old: str, new: str) -> None:
    Role.objects.filter(name=old).exclude(name=new).update(name=new)


def sync_default_roles(created_by=None):
    """
    Upsert system roles. Default permission sets are applied only when
    a role is first created so admin edits in the Roles UI are preserved.
    """
    _rename_role('Field Agent', ROLE_FIELD_AGENT)
    _rename_role('Delivery Agent', ROLE_DELIVERY_AGENT)

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

    manager, manager_created = Role.objects.update_or_create(
        name=ROLE_MANAGER,
        defaults={
            'description': 'Store operations — inventory, reports, finance (no user/role admin)',
            'is_system_role': True,
            'is_active': True,
            'created_by': created_by,
        },
    )
    if manager_created:
        manager.permissions.set(_manager_queryset())

    sales, sales_created = Role.objects.update_or_create(
        name=ROLE_SALES,
        defaults={
            'description': 'Front-line sales — POS, customers, catalog add (pricing set by manager)',
            'is_system_role': True,
            'is_active': True,
            'created_by': created_by,
        },
    )
    if sales_created:
        sales.permissions.set(_sales_queryset())

    field_agent, agent_created = Role.objects.update_or_create(
        name=ROLE_FIELD_AGENT,
        defaults={
            'description': 'Customer visits — map pin, site photos, visit orders and POS sales',
            'is_system_role': True,
            'is_active': True,
            'created_by': created_by,
        },
    )
    if agent_created:
        field_agent.permissions.set(_field_agent_queryset())

    dispatcher, dispatcher_created = Role.objects.update_or_create(
        name=ROLE_DISPATCHER,
        defaults={
            'description': 'Store dispatch — pack visit orders and assign delivery drivers',
            'is_system_role': True,
            'is_active': True,
            'created_by': created_by,
        },
    )
    if dispatcher_created:
        dispatcher.permissions.set(_dispatcher_queryset())

    delivery_agent, delivery_created = Role.objects.update_or_create(
        name=ROLE_DELIVERY_AGENT,
        defaults={
            'description': 'On-road delivery — map-first stops, lines, collect, POD',
            'is_system_role': True,
            'is_active': True,
            'created_by': created_by,
        },
    )
    if delivery_created:
        delivery_agent.permissions.set(_delivery_agent_queryset())

    # Deactivate legacy duplicate roles so the UI shows a clean trio.
    Role.objects.filter(name__in=LEGACY_ROLE_NAMES).update(is_active=False)

    return {
        ROLE_SUPER_ADMIN: super_admin,
        ROLE_MANAGER: manager,
        ROLE_SALES: sales,
        ROLE_FIELD_AGENT: field_agent,
        ROLE_DISPATCHER: dispatcher,
        ROLE_DELIVERY_AGENT: delivery_agent,
    }


def get_role_by_name(name: str) -> Optional[Role]:
    return Role.objects.filter(name=name, is_active=True).first()
