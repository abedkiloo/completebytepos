"""
Approved-only values for POS and reports — pending proposals never affect sellable state.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from django.apps import apps

from approvals.models import PendingChange
from approvals.permissions import is_maker_checker_enabled
from approvals.registry import (
    ACTION_PRODUCT_STOCK,
    ACTION_STOCK_ADJUST,
    ACTION_STOCK_PURCHASE,
    ACTION_STOCK_TRANSFER,
    PRICE_FIELDS,
    STOCK_FIELDS,
)

_PENDING_INVENTORY_STOCK_ACTIONS = (
    ACTION_STOCK_ADJUST,
    ACTION_STOCK_PURCHASE,
    ACTION_STOCK_TRANSFER,
)


def _pending_for_entity(entity_type: str, entity_id, action_types: tuple[str, ...] | None = None):
    qs = PendingChange.objects.filter(
        entity_type=entity_type,
        entity_id=str(entity_id),
        status=PendingChange.STATUS_PENDING,
    )
    if action_types:
        qs = qs.filter(action_type__in=action_types)
    return qs


def has_pending_product_price(product_id) -> bool:
    if not is_maker_checker_enabled():
        return False
    from approvals.registry import ACTION_PRODUCT_PRICE, ACTION_PRODUCT_TAX

    return _pending_for_entity(
        'products.Product',
        product_id,
        (ACTION_PRODUCT_PRICE, ACTION_PRODUCT_TAX),
    ).exists()


def has_pending_product_stock(product_id) -> bool:
    if not is_maker_checker_enabled():
        return False

    return _pending_for_entity(
        'products.Product',
        product_id,
        (ACTION_PRODUCT_STOCK,) + _PENDING_INVENTORY_STOCK_ACTIONS,
    ).exists()


def _collect_stock_caps(qs) -> list[int]:
    caps: list[int] = []
    for change in qs.only('proposed_values'):
        raw = (change.proposed_values or {}).get('stock_quantity')
        if raw is not None and raw != '':
            caps.append(int(raw))
    return caps


def _pending_proposed_stock_caps(product_id, variant_id=None) -> list[int]:
    """Proposed stock_quantity values from pending catalog or movement changes."""
    if not is_maker_checker_enabled():
        return []
    caps = _collect_stock_caps(
        _pending_for_entity(
            'products.Product',
            product_id,
            (ACTION_PRODUCT_STOCK,) + _PENDING_INVENTORY_STOCK_ACTIONS,
        )
    )
    if variant_id is not None:
        caps.extend(
            _collect_stock_caps(
                _pending_for_entity(
                    'products.ProductVariant',
                    variant_id,
                    (ACTION_PRODUCT_STOCK,),
                )
            )
        )
    return caps


def has_pending_product_deactivation(product_id) -> bool:
    if not is_maker_checker_enabled():
        return False
    from approvals.registry import ACTION_PRODUCT_DEACTIVATE

    return _pending_for_entity(
        'products.Product',
        product_id,
        (ACTION_PRODUCT_DEACTIVATE,),
    ).exists()


def has_pending_variant_price(variant_id) -> bool:
    if not is_maker_checker_enabled():
        return False
    from approvals.registry import ACTION_PRODUCT_PRICE

    return _pending_for_entity(
        'products.ProductVariant',
        variant_id,
        (ACTION_PRODUCT_PRICE,),
    ).exists()


def has_pending_variant_stock(variant_id) -> bool:
    if not is_maker_checker_enabled():
        return False

    return _pending_for_entity(
        'products.ProductVariant',
        variant_id,
        (ACTION_PRODUCT_STOCK,),
    ).exists()


def has_pending_variant_deactivation(variant_id) -> bool:
    if not is_maker_checker_enabled():
        return False
    from approvals.registry import ACTION_PRODUCT_DEACTIVATE

    return _pending_for_entity(
        'products.ProductVariant',
        variant_id,
        (ACTION_PRODUCT_DEACTIVATE,),
    ).exists()


def variant_pending_flags(variant_id) -> Dict[str, bool]:
    return {
        'pending_price': has_pending_variant_price(variant_id),
        'pending_stock': has_pending_variant_stock(variant_id),
        'pending_deactivation': has_pending_variant_deactivation(variant_id),
    }


def has_pending_category_deactivation(category_id) -> bool:
    if not is_maker_checker_enabled():
        return False
    from approvals.registry import ACTION_CATEGORY_DEACTIVATE

    return _pending_for_entity(
        'products.Category',
        category_id,
        (ACTION_CATEGORY_DEACTIVATE,),
    ).exists()


def category_pending_flags(category_id) -> Dict[str, bool]:
    return {
        'pending_deactivation': has_pending_category_deactivation(category_id),
    }


def product_pending_flags(product_id) -> Dict[str, bool]:
    return {
        'pending_price': has_pending_product_price(product_id),
        'pending_stock': has_pending_product_stock(product_id),
        'pending_deactivation': has_pending_product_deactivation(product_id),
    }


def apply_approved_product_overlay(product, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keep live (approved) price/stock in API payloads when a pending change exists.
    Adds ``pending_approval`` metadata for UI.
    """
    if not is_maker_checker_enabled():
        return data

    flags = product_pending_flags(product.pk)
    if not any(flags.values()):
        return data

    out = dict(data)
    out['pending_approval'] = {
        **flags,
        'message': 'Pending approval — changes not yet active',
    }
    if flags.get('pending_stock'):
        out['stock_quantity'] = approved_sellable_stock_quantity(product)
    return out


def apply_approved_variant_overlay(variant, data: Dict[str, Any]) -> Dict[str, Any]:
    if not is_maker_checker_enabled():
        return data

    flags = variant_pending_flags(variant.pk)
    if not any(flags.values()):
        return data

    out = dict(data)
    out['pending_approval'] = {
        **flags,
        'message': 'Pending approval — changes not yet active',
    }
    if flags.get('pending_stock'):
        caps = _pending_proposed_stock_caps(variant.product_id, variant_id=variant.pk)
        if caps:
            base = int(variant.stock_quantity or 0)
            out['stock_quantity'] = min([base, *caps])
    return out


def apply_approved_category_overlay(category, data: Dict[str, Any]) -> Dict[str, Any]:
    if not is_maker_checker_enabled():
        return data

    flags = category_pending_flags(category.pk)
    if not flags.get('pending_deactivation'):
        return data

    out = dict(data)
    out['pending_approval'] = {
        **flags,
        'message': 'Pending approval — deactivation not yet active',
    }
    return out


def approved_sellable_stock_quantity(product, variant=None) -> int:
    """
    Stock available for POS/checkout — live DB only, capped by pending decreases.
    Pending increases never inflate sellable quantity before approval.
    """
    from products.stock_utils import sellable_stock_quantity

    base = sellable_stock_quantity(product, variant=variant)
    variant_id = variant.pk if variant is not None else None
    caps = _pending_proposed_stock_caps(product.pk, variant_id=variant_id)
    if not caps:
        return base
    return min([base, *caps])


def sellable_price(product, variant=None) -> Decimal:
    """Price used at POS — always the approved row, never pending proposal."""
    from products.stock_utils import sellable_unit_price

    return sellable_unit_price(product, variant=variant)


def sellable_stock(product, variant=None) -> int:
    return approved_sellable_stock_quantity(product, variant=variant)
