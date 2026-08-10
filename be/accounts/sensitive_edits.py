"""
Who may change fields that affect revenue, inventory valuation, and reports.

Sales Personnel may add catalog items and run POS but must not change prices,
costs, stock levels, or sale-line price overrides.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

PRICING_FIELDS = ('price', 'mrp', 'cost', 'selling_price')
INVENTORY_REPORT_FIELDS = (
    'stock_quantity',
    'low_stock_threshold',
    'reorder_quantity',
    'track_stock',
)


def user_may_edit_financial_fields(user) -> bool:
    """True when the user may edit at least one pricing, cost, or stock field."""
    from products.catalog_access import user_may_edit_any_product_financial_field

    return user_may_edit_any_product_financial_field(user)


def user_may_view_audit_log(user) -> bool:
    """Same trust level as financial edits — managers review audit, not sales."""
    return user_may_edit_financial_fields(user)


def strip_sensitive_product_fields(
    data: Dict[str, Any],
    *,
    user,
    instance=None,
    is_create: bool = True,
) -> Dict[str, Any]:
    """Remove product fields the user is not permitted to write (per module settings)."""
    from products.catalog_access import strip_product_fields_by_access

    return strip_product_fields_by_access(
        data, user=user, instance=instance, is_create=is_create
    )


def sales_catalog_mode_active(user) -> bool:
    """True when the user edits catalog details only (no pricing/cost/stock fields)."""
    from products.catalog_access import (
        products_sales_catalog_access_enabled,
        user_may_edit_catalog_details,
        user_may_edit_product_pricing,
    )

    if user_may_edit_product_pricing(user):
        return False
    return user_may_edit_catalog_details(user) and products_sales_catalog_access_enabled()


def validate_sale_unit_price_override(
    user,
    *,
    product,
    variant,
    override,
) -> None:
    """
    Validate client-supplied unit_price on a sale line.

    Managers (product pricing editors) may set any non-negative price.
    Sales staff may charge the catalog selling price or higher (markup /
    customer-specific rate) but cannot undercut the catalog price.
    """
    from django.core.exceptions import ValidationError

    from products.stock_utils import sellable_unit_price

    if override is None:
        return
    from products.catalog_access import user_may_edit_product_pricing

    try:
        requested = Decimal(str(override))
    except Exception as exc:
        raise ValidationError('Invalid unit price.') from exc
    if requested < 0:
        raise ValidationError('Unit price cannot be negative.')

    if user_may_edit_product_pricing(user):
        return

    catalog_price = Decimal(str(sellable_unit_price(product, variant)))
    if requested < catalog_price:
        raise ValidationError(
            'Unit price cannot be below the selling price. '
            'Ask a manager if you need to discount this item.'
        )


def clamp_holding_financial_adjustments(
    user,
    tax_amount: Decimal,
    discount_amount: Decimal,
) -> tuple[Decimal, Decimal]:
    """Sales staff cannot set tax/discount on drafts (affects reported totals)."""
    if user_may_edit_financial_fields(user):
        return tax_amount, discount_amount
    return Decimal('0'), Decimal('0')
