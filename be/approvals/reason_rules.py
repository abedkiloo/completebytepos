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
    # Booleans like `track_stock` should be treated as an "initial set"
    # when moving from unset/False to True (not considered a change).
    if field == 'is_active':
        return False
    if field == 'track_stock':
        return (previous is None or previous is False) and bool(proposed)
    if field not in INITIAL_SET_NUMERIC_FIELDS:
        return False
    return is_unset_financial_value(previous) and not is_unset_financial_value(proposed)


def sensitive_values_equal(field: str, previous: Any, proposed: Any) -> bool:
    """True when the client re-submitted the same value (no real change)."""
    if field == 'is_active':
        return bool(previous) == bool(proposed)
    if field in INITIAL_SET_NUMERIC_FIELDS:
        if is_unset_financial_value(previous) and is_unset_financial_value(proposed):
            return True
        try:
            return Decimal(str(previous)) == Decimal(str(proposed))
        except (InvalidOperation, ValueError, TypeError):
            return str(previous) == str(proposed)
    return previous == proposed


def split_initial_vs_change_sensitive(
    instance,
    sensitive: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    initial: Dict[str, Any] = {}
    change: Dict[str, Any] = {}
    for key, value in sensitive.items():
        # If the instance doesn't have the attribute at all, treat this as
        # not applicable (ignore). Tests expect absent attributes like
        # `track_stock` on light-weight instances to be ignored.
        if not hasattr(instance, key):
            continue
        prev = _previous_field_value(instance, key)
        if sensitive_values_equal(key, prev, value):
            continue
        if is_initial_sensitive_set(key, prev, value):
            initial[key] = value
        else:
            change[key] = value
    return initial, change
