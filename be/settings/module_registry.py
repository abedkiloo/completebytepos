"""
Canonical module catalog for CompleteByte POS.

Single source of truth for:
  - init_modules (seed DB rows)
  - API catalog grouping (Module Settings UI)
  - Install presets (fresh setup + wizard)
  - Nav / feature documentation

Domains group modules by business capability — not by DB table names.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Domains (top-level classification)
# ---------------------------------------------------------------------------

DOMAINS: list[dict[str, Any]] = [
    {
        'id': 'commerce',
        'label': 'Sell & serve',
        'description': 'Checkout, customers, and invoicing.',
        'sort_order': 10,
    },
    {
        'id': 'catalog',
        'label': 'Catalog & buying',
        'description': 'Products, labels, and suppliers.',
        'sort_order': 20,
    },
    {
        'id': 'inventory',
        'label': 'Stock & warehouse',
        'description': 'Quantities, movements, and replenishment.',
        'sort_order': 30,
    },
    {
        'id': 'finance',
        'label': 'Money & accounting',
        'description': 'Expenses, income, banks, and books.',
        'sort_order': 40,
    },
    {
        'id': 'insights',
        'label': 'Insights',
        'description': 'Reports and business analytics.',
        'sort_order': 50,
    },
    {
        'id': 'people',
        'label': 'People',
        'description': 'Staff and HR-style records.',
        'sort_order': 60,
    },
    {
        'id': 'platform',
        'label': 'Platform',
        'description': 'Users, roles, branches, and system toggles.',
        'sort_order': 70,
    },
]

DOMAIN_BY_ID = {d['id']: d for d in DOMAINS}

# Modules folded under a parent in the UI (legacy duplicate rows in DB).
ROLLUP_UNDER: dict[str, str] = {
    'balance_sheet': 'accounting',
    'trial_balance': 'accounting',
    'cash_flow': 'accounting',
    'account_statement': 'accounting',
}

# ---------------------------------------------------------------------------
# Module definitions
# ---------------------------------------------------------------------------

def _f(key, name, description='', order=0, enabled=True):
    return {
        'key': key,
        'name': name,
        'description': description,
        'order': order,
        'enabled_by_default': enabled,
    }


MODULE_DEFINITIONS: list[dict[str, Any]] = [
    # --- Commerce ---
    {
        'module_name': 'sales',
        'domain': 'commerce',
        'display_name': 'Sales',
        'description': 'Point of sale, billing desk, and sales history.',
        'default_enabled': True,
        'sort_order': 10,
        'features': [
            _f('pos', 'Retail POS', 'Fast walk-in checkout.', 1),
            _f('billing_pos', 'Billing POS', 'Invoices, credit, and held carts.', 2),
            _f('normal_sale', 'Normal sale', 'Full sale with delivery fields.', 3, enabled=False),
            _f('sales_history', 'Sales history', 'Search past transactions.', 4),
            _f('receipt_printing', 'Receipt printing', 'Print or reprint receipts.', 5),
        ],
    },
    {
        'module_name': 'customers',
        'domain': 'commerce',
        'display_name': 'Customers',
        'description': 'CRM, balances, and walk-in profiles.',
        'default_enabled': True,
        'sort_order': 20,
        'features': [
            _f('customer_management', 'Customer records', '', 1),
            _f('customer_history', 'Purchase history', '', 2),
            _f('customer_reports', 'Customer reports', '', 3, enabled=False),
        ],
    },
    {
        'module_name': 'invoicing',
        'domain': 'commerce',
        'display_name': 'Invoicing',
        'description': 'Formal invoices and payment plans.',
        'default_enabled': False,
        'sort_order': 30,
        'features': [
            _f('invoice_creation', 'Create invoices', '', 1),
            _f('invoice_tracking', 'Track status', '', 2),
            _f('payment_tracking', 'Record payments', '', 3),
            _f('partial_payments', 'Partial payments', '', 4),
            _f('invoice_reports', 'Invoice reports', '', 5, enabled=False),
        ],
    },
    # --- Catalog ---
    {
        'module_name': 'products',
        'domain': 'catalog',
        'display_name': 'Products',
        'description': 'SKU catalog, pricing, and categories.',
        'default_enabled': True,
        'sort_order': 10,
        'features': [
            _f('barcode_printing', 'Barcode printing', '', 1),
            _f('qr_printing', 'QR printing', '', 2, enabled=False),
            _f('product_variants', 'Variants (size/color)', '', 3, enabled=False),
            _f('product_images', 'Product images', '', 4, enabled=False),
            _f('bulk_operations', 'Bulk actions', '', 5),
            _f('csv_import_export', 'CSV import/export', '', 6),
        ],
    },
    {
        'module_name': 'barcodes',
        'domain': 'catalog',
        'display_name': 'Barcodes & labels',
        'description': 'Generate and print product labels.',
        'default_enabled': False,
        'sort_order': 20,
        'features': [
            _f('barcode_generation', 'Barcodes', '', 1),
            _f('qr_generation', 'QR codes', '', 2),
            _f('label_printing', 'Label printing', '', 3),
            _f('bulk_generation', 'Bulk generation', '', 4),
        ],
    },
    {
        'module_name': 'suppliers',
        'domain': 'catalog',
        'display_name': 'Suppliers',
        'description': 'Vendors and purchase relationships.',
        'default_enabled': False,
        'sort_order': 30,
        'features': [
            _f('supplier_management', 'Supplier records', '', 1),
            _f('supplier_products', 'Supplier products', '', 2, enabled=False),
            _f('supplier_reports', 'Supplier reports', '', 3, enabled=False),
        ],
    },
    # --- Inventory ---
    {
        'module_name': 'inventory',
        'domain': 'inventory',
        'display_name': 'Inventory',
        'description': 'Stock levels, movements, and alerts.',
        'default_enabled': True,
        'sort_order': 10,
        'features': [
            _f('stock_adjustments', 'Adjustments', '', 1),
            _f('stock_transfers', 'Transfers', '', 2),
            _f('low_stock_alerts', 'Low stock alerts', '', 3),
            _f('reorder_points', 'Reorder points', '', 4, enabled=False),
            _f('inventory_reports', 'Inventory reports', '', 5),
        ],
    },
    {
        'module_name': 'stock',
        'domain': 'inventory',
        'display_name': 'Stock operations',
        'description': 'Operational stock screens in the menu.',
        'default_enabled': True,
        'sort_order': 20,
        'features': [
            _f('manage_stock', 'Manage stock', '', 1),
            _f('stock_adjustments', 'Adjustments', '', 2),
            _f('stock_transfers', 'Transfers', '', 3),
            _f('stock_reports', 'Stock reports', '', 4),
            _f('low_stock_alerts', 'Low stock alerts', '', 5),
        ],
    },
    # --- Finance ---
    {
        'module_name': 'expenses',
        'domain': 'finance',
        'display_name': 'Expenses',
        'description': 'Track money going out.',
        'default_enabled': False,
        'sort_order': 10,
        'features': [],
    },
    {
        'module_name': 'income',
        'domain': 'finance',
        'display_name': 'Income',
        'description': 'Non-POS revenue streams.',
        'default_enabled': False,
        'sort_order': 20,
        'features': [],
    },
    {
        'module_name': 'bank_accounts',
        'domain': 'finance',
        'display_name': 'Bank accounts',
        'description': 'Cash and bank balances.',
        'default_enabled': False,
        'sort_order': 30,
        'features': [],
    },
    {
        'module_name': 'money_transfer',
        'domain': 'finance',
        'display_name': 'Transfers',
        'description': 'Move funds between accounts.',
        'default_enabled': False,
        'sort_order': 40,
        'features': [],
    },
    {
        'module_name': 'accounting',
        'domain': 'finance',
        'display_name': 'Accounting',
        'description': 'Chart of accounts, journals, and financial statements.',
        'default_enabled': False,
        'sort_order': 50,
        'features': [
            _f('chart_of_accounts', 'Chart of accounts', '', 1),
            _f('journal_entries', 'Journal entries', '', 2),
            _f('balance_sheet', 'Balance sheet', '', 3),
            _f('income_statement', 'Income statement (P&L)', '', 4),
            _f('trial_balance', 'Trial balance', '', 5),
            _f('general_ledger', 'General ledger', '', 6),
        ],
    },
    # Legacy standalone accounting report modules (kept for DB compat; hidden by preset)
    {
        'module_name': 'balance_sheet',
        'domain': 'finance',
        'display_name': 'Balance sheet (legacy)',
        'description': 'Use Accounting module instead.',
        'default_enabled': False,
        'sort_order': 901,
        'rollup_under': 'accounting',
        'features': [],
    },
    {
        'module_name': 'trial_balance',
        'domain': 'finance',
        'display_name': 'Trial balance (legacy)',
        'description': 'Use Accounting module instead.',
        'default_enabled': False,
        'sort_order': 902,
        'rollup_under': 'accounting',
        'features': [],
    },
    {
        'module_name': 'cash_flow',
        'domain': 'finance',
        'display_name': 'Cash flow (legacy)',
        'description': 'Use Accounting module instead.',
        'default_enabled': False,
        'sort_order': 903,
        'rollup_under': 'accounting',
        'features': [],
    },
    {
        'module_name': 'account_statement',
        'domain': 'finance',
        'display_name': 'Account statement (legacy)',
        'description': 'Use Accounting module instead.',
        'default_enabled': False,
        'sort_order': 904,
        'rollup_under': 'accounting',
        'features': [],
    },
    # --- Insights ---
    {
        'module_name': 'reports',
        'domain': 'insights',
        'display_name': 'Reports',
        'description': 'Sales, product, and inventory analytics.',
        'default_enabled': False,
        'sort_order': 10,
        'features': [
            _f('sales_reports', 'Sales reports', '', 1),
            _f('product_reports', 'Product reports', '', 2),
            _f('inventory_reports', 'Inventory reports', '', 3),
            _f('financial_reports', 'Financial reports', '', 4),
        ],
    },
    # --- People ---
    {
        'module_name': 'employees',
        'domain': 'people',
        'display_name': 'Employees',
        'description': 'Staff records (optional).',
        'default_enabled': False,
        'sort_order': 10,
        'features': [
            _f('employee_management', 'Employee records', '', 1),
            _f('employee_reports', 'Reports', '', 2, enabled=False),
        ],
    },
    # --- Platform ---
    {
        'module_name': 'settings',
        'domain': 'platform',
        'display_name': 'System settings',
        'description': 'Users, roles, modules, and branches.',
        'default_enabled': True,
        'sort_order': 10,
        'features': [
            _f('user_management', 'User management', '', 1),
            _f('role_management', 'Role management', '', 2),
            _f('permission_management', 'Permissions', '', 3),
            _f('module_settings', 'Module settings', '', 4),
            _f('system_configuration', 'Store configuration', '', 5),
            _f('multi_branch_support', 'Multi-branch', 'Branch selector in header.', 6, enabled=False),
        ],
    },
]

MODULE_BY_NAME = {m['module_name']: m for m in MODULE_DEFINITIONS}

PRIMARY_MODULE_NAMES = [
    m['module_name']
    for m in MODULE_DEFINITIONS
    if not m.get('rollup_under')
]

# ---------------------------------------------------------------------------
# Install / settings presets
# ---------------------------------------------------------------------------

PRESETS: dict[str, dict[str, Any]] = {
    'retail_starter': {
        'id': 'retail_starter',
        'label': 'Retail starter',
        'description': 'Billing desk, products, customers, and stock — lean setup for new stores.',
        'sort_order': 1,
        'modules': {
            'products': True,
            'sales': True,
            'customers': True,
            'inventory': True,
            'stock': True,
            'settings': True,
        },
        'features': {
            # No retail POS, normal sale, or barcode module in the starter pack.
            'sales': ['billing_pos', 'receipt_printing', 'sales_history'],
            'products': ['bulk_operations', 'csv_import_export'],
            'customers': ['customer_management', 'customer_history'],
            'inventory': ['stock_adjustments', 'low_stock_alerts', 'inventory_reports'],
            'stock': ['manage_stock', 'stock_adjustments', 'low_stock_alerts'],
            'settings': [
                'user_management',
                'role_management',
                'permission_management',
                'module_settings',
            ],
        },
        'disable_unlisted': True,
    },
    'retail_full': {
        'id': 'retail_full',
        'label': 'Full retail',
        'description': 'Starter plus POS, barcodes, invoicing, suppliers, and reports.',
        'sort_order': 2,
        'extends': 'retail_starter',
        'modules': {
            'invoicing': True,
            'suppliers': True,
            'barcodes': True,
            'reports': True,
        },
        'features': {
            'sales': ['pos', 'normal_sale'],
            'products': ['barcode_printing'],
            'invoicing': ['invoice_creation', 'invoice_tracking', 'payment_tracking'],
            'suppliers': ['supplier_management'],
            'barcodes': ['barcode_generation', 'label_printing'],
            'reports': ['sales_reports', 'product_reports', 'inventory_reports'],
        },
        'disable_unlisted': False,
    },
    'finance_pack': {
        'id': 'finance_pack',
        'label': 'Finance pack',
        'description': 'Expenses, income, and accounting on top of retail.',
        'sort_order': 3,
        'modules': {
            'expenses': True,
            'income': True,
            'accounting': True,
            'reports': True,
        },
        'features': {
            'accounting': [
                'chart_of_accounts',
                'journal_entries',
                'balance_sheet',
                'income_statement',
                'trial_balance',
            ],
            'reports': ['sales_reports', 'financial_reports'],
        },
        'disable_unlisted': False,
    },
}


def get_preset_manifest() -> list[dict[str, Any]]:
    return [
        {
            'id': p['id'],
            'label': p['label'],
            'description': p['description'],
            'sort_order': p.get('sort_order', 99),
        }
        for p in sorted(PRESETS.values(), key=lambda x: x.get('sort_order', 99))
    ]


def resolve_preset(preset_id: str) -> dict[str, Any]:
    """Merge preset with its `extends` chain."""
    base = PRESETS.get(preset_id)
    if not base:
        raise ValueError(f'Unknown preset: {preset_id}')

    modules: dict[str, bool] = {}
    features: dict[str, list[str]] = {}
    disable_unlisted = base.get('disable_unlisted', False)

    chain: list[str] = []
    current = preset_id
    seen = set()
    while current and current not in seen:
        seen.add(current)
        chain.insert(0, current)
        parent = PRESETS.get(current, {}).get('extends')
        current = parent

    for pid in chain:
        p = PRESETS[pid]
        modules.update(p.get('modules', {}))
        for mod, feats in p.get('features', {}).items():
            features.setdefault(mod, [])
            features[mod] = list(dict.fromkeys(features[mod] + feats))
        if p.get('disable_unlisted'):
            disable_unlisted = True

    return {
        'id': preset_id,
        'modules': modules,
        'features': features,
        'disable_unlisted': disable_unlisted,
    }


# ---------------------------------------------------------------------------
# Permission rows (accounts.Permission.module) → catalog domain / module
# ---------------------------------------------------------------------------

# Permission.module keys that belong to each business domain (for Roles UI).
PERMISSION_MODULE_DOMAIN: dict[str, str] = {
    'products': 'catalog',
    'categories': 'catalog',
    'suppliers': 'catalog',
    'barcodes': 'catalog',
    'sales': 'commerce',
    'pos': 'commerce',
    'customers': 'commerce',
    'invoicing': 'commerce',
    'inventory': 'inventory',
    'stock': 'inventory',
    'expenses': 'finance',
    'income': 'finance',
    'bank_accounts': 'finance',
    'money_transfer': 'finance',
    'accounting': 'finance',
    'balance_sheet': 'finance',
    'trial_balance': 'finance',
    'cash_flow': 'finance',
    'account_statement': 'finance',
    'reports': 'insights',
    'employees': 'people',
    'users': 'platform',
    'roles': 'platform',
    'settings': 'platform',
    'modules': 'platform',
}

# Tie permission modules to a catalog module for display (defaults to self).
PERMISSION_CATALOG_MODULE: dict[str, str] = {
    'categories': 'products',
    'pos': 'sales',
    'users': 'settings',
    'roles': 'settings',
    'modules': 'settings',
    'balance_sheet': 'accounting',
    'trial_balance': 'accounting',
    'cash_flow': 'accounting',
    'account_statement': 'accounting',
}


def get_permission_domain_info(permission_module: str) -> dict[str, str]:
    """Resolve domain + catalog module labels for a permission row."""
    domain_id = PERMISSION_MODULE_DOMAIN.get(permission_module, 'platform')
    domain = DOMAIN_BY_ID.get(domain_id, {'id': domain_id, 'label': domain_id.title()})
    catalog_key = PERMISSION_CATALOG_MODULE.get(permission_module, permission_module)
    catalog_def = MODULE_BY_NAME.get(catalog_key, {})
    return {
        'domain': domain_id,
        'domain_label': domain.get('label', domain_id),
        'catalog_module': catalog_key,
        'catalog_module_label': catalog_def.get('display_name', catalog_key.replace('_', ' ').title()),
    }
