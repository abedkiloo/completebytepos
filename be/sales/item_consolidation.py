"""Merge duplicate sale line payloads (same product + variant)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple


def _normalize_unit_price(unit_price: Any) -> Optional[Decimal]:
    if unit_price is None or unit_price == '':
        return None
    try:
        return Decimal(str(unit_price)).quantize(Decimal('0.01'))
    except Exception:
        return None


def _line_key(
    product_id: Any, variant_id: Any, unit_price: Any = None
) -> Tuple[int, Optional[int], Optional[str]]:
    """Same product + variant + unit price merge together; different prices stay separate."""
    price = _normalize_unit_price(unit_price)
    price_key = format(price, 'f') if price is not None else None
    return (
        int(product_id),
        int(variant_id) if variant_id not in (None, '') else None,
        price_key,
    )


def consolidate_sale_items_data(items_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sum quantities for rows with the same product_id, variant_id, and unit_price.
    Different unit prices stay as separate lines (e.g. catalog vs markup sale).
    """
    if not items_data:
        return []

    merged: Dict[Tuple[int, Optional[int], Optional[str]], Dict[str, Any]] = {}
    for item in items_data:
        product_id = item.get('product_id')
        if not product_id:
            continue
        unit_price = item.get('unit_price')
        key = _line_key(product_id, item.get('variant_id'), unit_price)
        qty = int(item.get('quantity', 1) or 1)
        if qty <= 0:
            continue
        if key in merged:
            merged[key]['quantity'] = int(merged[key]['quantity']) + qty
        else:
            merged[key] = {
                'product_id': int(product_id),
                'variant_id': key[1],
                'quantity': qty,
            }
            if unit_price is not None and unit_price != '':
                merged[key]['unit_price'] = unit_price

    return list(merged.values())
