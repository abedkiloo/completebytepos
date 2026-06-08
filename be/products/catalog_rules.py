"""Catalog rules when sales staff add products without pricing."""

from accounts.sensitive_edits import (
    PRICING_FIELDS,
    sales_catalog_mode_active,
    strip_sensitive_product_fields,
)

# Re-export for existing imports
__all__ = [
    'PRICING_FIELDS',
    'sales_catalog_mode_active',
    'apply_sales_catalog_rules',
]


def apply_sales_catalog_rules(data, *, user, is_create=True, instance=None):
    """Strip product fields the user cannot write (role + Products module settings)."""
    return strip_sensitive_product_fields(
        data, user=user, instance=instance, is_create=is_create
    )
