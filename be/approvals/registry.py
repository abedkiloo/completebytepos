"""
Sensitive action types that require maker-checker when enabled.

Each action maps to a checker permission module (uses existing ``approve`` verb).
"""

from __future__ import annotations

from typing import FrozenSet

# Product / catalog
ACTION_PRODUCT_PRICE = 'product_price'
ACTION_PRODUCT_STOCK = 'product_stock'
ACTION_PRODUCT_DEACTIVATE = 'product_deactivate'
ACTION_PRODUCT_DELETE = 'product_delete'
ACTION_PRODUCT_UNIT = 'product_unit'
ACTION_PRODUCT_TAX = 'product_tax'

# Categories
ACTION_CATEGORY_DEACTIVATE = 'category_deactivate'
ACTION_CATEGORY_DELETE = 'category_delete'

# Inventory movements (manual)
ACTION_STOCK_ADJUST = 'stock_adjust'
ACTION_STOCK_PURCHASE = 'stock_purchase'
ACTION_STOCK_TRANSFER = 'stock_transfer'

# Financial / store
ACTION_STORE_SETTINGS = 'store_settings'
ACTION_PAYMENT_METHODS = 'payment_methods'
ACTION_RECEIPT_LEGAL = 'receipt_legal'

# Access control
ACTION_ROLE_PERMISSIONS = 'role_permissions'

# Sales (completed)
ACTION_SALE_COMPLETED_EDIT = 'sale_completed_edit'

PRODUCT_SENSITIVE_FIELDS: FrozenSet[str] = frozenset({
    'price',
    'mrp',
    'cost',
    'selling_price',
    'stock_quantity',
    'is_active',
})

PRICE_FIELDS: FrozenSet[str] = frozenset({'price', 'mrp', 'cost', 'selling_price', 'tax_rate'})

STOCK_FIELDS: FrozenSet[str] = frozenset({
    'stock_quantity',
    'low_stock_threshold',
    'reorder_quantity',
    'track_stock',
})

VARIANT_SENSITIVE_FIELDS: FrozenSet[str] = frozenset({
    'price',
    'mrp',
    'cost',
    'selling_price',
    'stock_quantity',
    'is_active',
})

CHECKER_MODULE_BY_ACTION: dict[str, str] = {
    ACTION_PRODUCT_PRICE: 'products',
    ACTION_PRODUCT_STOCK: 'inventory',
    ACTION_PRODUCT_DEACTIVATE: 'products',
    ACTION_PRODUCT_DELETE: 'products',
    ACTION_PRODUCT_UNIT: 'products',
    ACTION_PRODUCT_TAX: 'products',
    ACTION_CATEGORY_DEACTIVATE: 'products',
    ACTION_CATEGORY_DELETE: 'products',
    ACTION_STOCK_ADJUST: 'inventory',
    ACTION_STOCK_PURCHASE: 'inventory',
    ACTION_STOCK_TRANSFER: 'inventory',
    ACTION_STORE_SETTINGS: 'settings',
    ACTION_PAYMENT_METHODS: 'settings',
    ACTION_RECEIPT_LEGAL: 'settings',
    ACTION_ROLE_PERMISSIONS: 'roles',
    ACTION_SALE_COMPLETED_EDIT: 'sales',
}


def classify_product_field_changes(proposed: dict) -> list[str]:
    """Return action types implied by a product patch/create payload."""
    actions: list[str] = []
    keys = set(proposed.keys())
    if keys & PRICE_FIELDS:
        actions.append(ACTION_PRODUCT_PRICE)
    if keys & STOCK_FIELDS:
        actions.append(ACTION_PRODUCT_STOCK)
    if 'is_active' in keys and proposed.get('is_active') is False:
        actions.append(ACTION_PRODUCT_DEACTIVATE)
    if 'unit' in keys:
        actions.append(ACTION_PRODUCT_UNIT)
    if 'tax_rate' in keys:
        actions.append(ACTION_PRODUCT_TAX)
    return actions


def classify_variant_field_changes(proposed: dict) -> list[str]:
    """Variant rows use the same action types as products (no tax/unit on variants)."""
    return classify_product_field_changes(
        {k: v for k, v in proposed.items() if k in VARIANT_SENSITIVE_FIELDS}
    )
