"""Normalize invoice line payloads from the API / frontend."""

from __future__ import annotations

from typing import Any


def resolve_product_id(item_data: dict[str, Any]) -> int | None:
    """Accept product_id or product (id) from clients."""
    raw = item_data.get('product_id')
    if raw is None:
        raw = item_data.get('product')
    if raw is None or raw == '':
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def normalize_invoice_items(items_data: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Return copies with product_id set for downstream create logic."""
    normalized: list[dict[str, Any]] = []
    for item in items_data or []:
        if not isinstance(item, dict):
            continue
        copy = dict(item)
        product_id = resolve_product_id(copy)
        if product_id is not None:
            copy['product_id'] = product_id
        normalized.append(copy)
    return normalized
