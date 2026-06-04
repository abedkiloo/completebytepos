"""Optional post-completion sale controls (P3 — off by default)."""

from __future__ import annotations

from typing import Any, Dict, FrozenSet

from approvals.permissions import is_maker_checker_enabled

# v1 optional queue: metadata only — not line items or totals.
SALE_EDIT_QUEUEABLE_FIELDS: FrozenSet[str] = frozenset({'notes', 'payment_method'})

COMPLETED_SALE_IMMUTABLE_MESSAGE = (
    'Completed sales cannot be edited. Enable optional sales controls in store settings '
    'for future post-completion approvals, or use a dedicated refund/void flow when available.'
)

SALE_EDIT_NOT_AVAILABLE_MESSAGE = (
    'Editing totals, line items, or discounts on completed sales is not available yet.'
)


def is_sales_maker_checker_active(store=None) -> bool:
    """True only when global MC and optional sales controls are both on."""
    if not is_maker_checker_enabled():
        return False
    if store is None:
        from settings.models import StoreSettings

        store = StoreSettings.load()
    return bool(getattr(store, 'maker_checker_sales_controls', False))


def completed_sale_direct_edit_blocked(store=None) -> bool:
    """Default policy: block API edits to completed sales unless optional mode is on."""
    return not is_sales_maker_checker_active(store)


def filter_queueable_sale_fields(proposed: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in proposed.items() if k in SALE_EDIT_QUEUEABLE_FIELDS}


def sale_edit_has_unsupported_fields(proposed: Dict[str, Any]) -> bool:
    if not proposed:
        return False
    return bool(set(proposed.keys()) - SALE_EDIT_QUEUEABLE_FIELDS)
