"""Merge duplicate sale line payloads (same product + variant)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple


def _line_key(product_id: Any, variant_id: Any) -> Tuple[int, Optional[int]]:
    return int(product_id), int(variant_id) if variant_id not in (None, '') else None


def consolidate_sale_items_data(items_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sum quantities for rows with the same product_id and variant_id.
    Prevents duplicate SaleItem rows when clients send split cart lines.
    """
    if not items_data:
        return []

    merged: Dict[Tuple[int, Optional[int]], Dict[str, Any]] = {}
    for item in items_data:
        product_id = item.get('product_id')
        if not product_id:
            continue
        key = _line_key(product_id, item.get('variant_id'))
        qty = int(item.get('quantity', 1) or 1)
        if qty <= 0:
            continue
        unit_price = item.get('unit_price')
        if key in merged:
            merged[key]['quantity'] = int(merged[key]['quantity']) + qty
            if unit_price is not None:
                merged[key]['unit_price'] = unit_price
        else:
            merged[key] = {
                'product_id': int(product_id),
                'variant_id': key[1],
                'quantity': qty,
            }
            if unit_price is not None:
                merged[key]['unit_price'] = unit_price

    return list(merged.values())
