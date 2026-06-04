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
    """Managers and super admins may edit pricing, costs, and stock quantities."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser or user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    if profile.role in ('super_admin', 'manager'):
        return True
    custom = getattr(profile, 'custom_role', None)
    if custom and custom.name in ('Super Admin', 'Manager'):
        return True
    return False


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
    """Remove pricing and inventory fields sales staff must not write."""
    if user_may_edit_financial_fields(user):
        return data

    for key in PRICING_FIELDS:
        data.pop(key, None)

    if is_create:
        data['price'] = Decimal('0')
        data['mrp'] = Decimal('0')
        data['cost'] = Decimal('0')
    else:
        for key in INVENTORY_REPORT_FIELDS:
            data.pop(key, None)

    return data


def sales_catalog_mode_active(user) -> bool:
    """True when store flags ask the UI to hide pricing for sales (optional layer)."""
    from settings.models import StoreSettings

    if user_may_edit_financial_fields(user):
        return False
    store = StoreSettings.load()
    return bool(store.allow_sales_add_products and store.sales_catalog_skip_pricing)


def validate_sale_unit_price_override(
    user,
    *,
    product,
    variant,
    override,
) -> None:
    """Reject client-supplied unit_price overrides from sales staff."""
    from django.core.exceptions import ValidationError

    from products.stock_utils import sellable_unit_price

    if override is None:
        return
    if user_may_edit_financial_fields(user):
        return
    catalog_price = sellable_unit_price(product, variant)
    try:
        requested = Decimal(str(override))
    except Exception as exc:
        raise ValidationError('Invalid unit price.') from exc
    if requested != Decimal(str(catalog_price)):
        raise ValidationError(
            'You cannot change unit prices on sales. Ask a manager to adjust product pricing.'
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
