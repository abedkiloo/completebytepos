"""When maker-checker reasons are required (changes only, not initial values)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Tuple

INITIAL_SET_NUMERIC_FIELDS = frozenset({
    'price',
    'selling_price',
    'mrp',
    'cost',
    'stock_quantity',
    'low_stock_threshold',
    'reorder_quantity',
})


def is_unset_financial_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == '':
        return True
    try:
        return Decimal(str(value)) == 0
    except (InvalidOperation, ValueError, TypeError):
        return False


def _previous_field_value(instance, field: str) -> Any:
    if field == 'selling_price':
        return getattr(instance, 'price', None)
    return getattr(instance, field, None)


def is_initial_sensitive_set(field: str, previous: Any, proposed: Any) -> bool:
    """True when moving from empty/zero to a first non-zero value (not a change)."""
    if field in ('is_active', 'track_stock', 'unit', 'tax_rate'):
        return False
    if field not in INITIAL_SET_NUMERIC_FIELDS:
        return False
    return is_unset_financial_value(previous) and not is_unset_financial_value(proposed)


def split_initial_vs_change_sensitive(
    instance,
    sensitive: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    initial: Dict[str, Any] = {}
    change: Dict[str, Any] = {}
    for key, value in sensitive.items():
        prev = _previous_field_value(instance, key)
        if is_initial_sensitive_set(key, prev, value):
            initial[key] = value
        else:
            change[key] = value
    return initial, change
