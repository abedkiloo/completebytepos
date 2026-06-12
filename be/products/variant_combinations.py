"""Explicit size/color variant pairs (not always a full cartesian matrix)."""

import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from products.models import Color, Product, ProductVariant, Size
from products.stock_utils import sync_product_stock_from_variants


def _nullable_int(value: Any) -> Optional[int]:
    if value in (None, '', 'none', 'null'):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_variant_combinations(raw: Any) -> List[Dict[str, Optional[int]]]:
    """
    Parse client payload into ``[{'size': id|None, 'color': id|None}, ...]``.
    Accepts JSON string, list of dicts, or list of ``[size, color]`` pairs.
    """
    if raw is None or raw == '':
        return []
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        return []

    pairs: List[Dict[str, Optional[int]]] = []
    seen: set = set()
    for item in raw:
        if isinstance(item, dict):
            size_id = _nullable_int(item.get('size', item.get('size_id')))
            color_id = _nullable_int(item.get('color', item.get('color_id')))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            size_id = _nullable_int(item[0])
            color_id = _nullable_int(item[1])
        else:
            continue
        if size_id is None and color_id is None:
            continue
        key = (size_id, color_id)
        if key in seen:
            continue
        seen.add(key)
        pairs.append({'size': size_id, 'color': color_id})
    return pairs


def combination_pairs(combinations: Sequence[Dict[str, Optional[int]]]) -> List[Tuple[Optional[int], Optional[int]]]:
    return [(c.get('size'), c.get('color')) for c in combinations]


def sync_product_variant_combinations(
    product: Product,
    combinations: Sequence[Dict[str, Optional[int]]],
) -> List[ProductVariant]:
    """
  Create, keep, or remove variant rows so they match ``combinations`` exactly.
  Also syncs ``available_sizes`` / ``available_colors`` to the union of used ids.
  """
    from products.services import ProductVariantService

    if not product.has_variants:
        return []

    wanted = set(combination_pairs(combinations))
    size_ids = {s for s, _ in wanted if s}
    color_ids = {c for _, c in wanted if c}
    product.available_sizes.set(size_ids)
    product.available_colors.set(color_ids)

    service = ProductVariantService()
    existing = list(ProductVariant.objects.filter(product=product))
    existing_map = {(v.size_id, v.color_id): v for v in existing}

    for key, variant in list(existing_map.items()):
        if key not in wanted:
            variant.delete()

    created: List[ProductVariant] = []
    for size_id, color_id in wanted:
        if ProductVariant.objects.filter(
            product=product, size_id=size_id, color_id=color_id
        ).exists():
            continue
        size = Size.objects.filter(pk=size_id).first() if size_id else None
        color = Color.objects.filter(pk=color_id).first() if color_id else None
        created.append(service._create_variant(product, size, color))

    if product.track_stock:
        sync_product_stock_from_variants(product)
    return created
