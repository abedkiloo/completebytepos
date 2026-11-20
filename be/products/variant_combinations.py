"""Explicit size/color variant pairs (not always a full cartesian matrix)."""

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

from products.models import Color, Product, ProductVariant, Size
from products.stock_utils import sync_product_cost_from_variants, sync_product_stock_from_variants

_MONEY_MAX = Decimal('99999999.99')
_QTY_MAX = 1000000


def _nullable_int(value: Any) -> Optional[int]:
    if value in (None, '', 'none', 'null'):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_money(value: Any) -> Optional[Decimal]:
    """
    Parse one money amount from a combination row.

    Args:
        value: Number or numeric string. Empty and null are missing.

    Returns:
        Decimal from 0 to 99999999.99, or None when missing or out of range.

    Raises:
        None. Bad text returns None.
    """
    if value in (None, ''):
        return None
    try:
        amount = Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        return None
    if amount < 0 or amount > _MONEY_MAX:
        return None
    return amount


def _optional_qty(value: Any) -> Optional[int]:
    """
    Parse one whole-number count from a combination row.

    Args:
        value: Integer or numeric string. Empty and null are missing.

    Returns:
        int from 0 to 1000000, or None when missing or out of range.

    Raises:
        None. Bad text returns None.
    """
    if value in (None, ''):
        return None
    try:
        qty = int(value)
    except (TypeError, ValueError):
        return None
    if qty < 0 or qty > _QTY_MAX:
        return None
    return qty


def normalize_variant_combinations(raw: Any) -> List[Dict[str, Any]]:
    """
    Parse client payload into size/colour rows, keeping price, cost, and stock.

    Args:
        raw: JSON string, list of dicts, or list of ``[size, color]`` pairs.
            Empty, null, and non-lists become an empty list. At most the
            rows the client sent.

    Returns:
        List of dicts with ``size`` and ``color`` (id or None). A dict row
        may also include ``price``, ``mrp``, ``cost``, ``stock_quantity``,
        and ``low_stock_threshold`` when those values are in range.

    Raises:
        json.JSONDecodeError: ``raw`` is a string that is not JSON.
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
        row: Dict[str, Any] = {'size': size_id, 'color': color_id}
        if isinstance(item, dict):
            price = _optional_money(item.get('price', item.get('selling_price')))
            mrp = _optional_money(item.get('mrp'))
            cost = _optional_money(item.get('cost'))
            stock = _optional_qty(item.get('stock_quantity'))
            threshold = _optional_qty(item.get('low_stock_threshold'))
            if price is not None:
                row['price'] = price
            if mrp is not None:
                row['mrp'] = mrp
            if cost is not None:
                row['cost'] = cost
            if stock is not None:
                row['stock_quantity'] = stock
            if threshold is not None:
                row['low_stock_threshold'] = threshold
        pairs.append(row)
    return pairs


def combination_pairs(combinations: Sequence[Dict[str, Optional[int]]]) -> List[Tuple[Optional[int], Optional[int]]]:
    return [(c.get('size'), c.get('color')) for c in combinations]


def _apply_new_variant_amounts(variant: ProductVariant, combo: Dict[str, Any]) -> None:
    """
    Write the price, cost, MRP, and opening count onto a variant just created.

    Args:
        variant: New size and colour. Its count is still 0.
        combo: Combination row. Money fields are 0–99999999.99. Counts are
            0–1000000. Missing fields keep the value copied from the product.

    Returns:
        None. A positive ``stock_quantity`` writes one OPENING purchase so
        the count is the number the person typed.

    Raises:
        ValidationError: The opening movement cannot be stored.
    """
    fields = []
    if combo.get('price') is not None:
        variant.price = combo['price']
        fields.append('price')
    if combo.get('mrp') is not None:
        variant.mrp = combo['mrp']
        fields.append('mrp')
    cost = combo.get('cost')
    if cost is not None and cost > 0:
        variant.cost = cost
        fields.append('cost')
    if combo.get('low_stock_threshold') is not None:
        variant.low_stock_threshold = combo['low_stock_threshold']
        fields.append('low_stock_threshold')
    if fields:
        variant.save(update_fields=fields)

    qty = combo.get('stock_quantity')
    if qty is None or qty <= 0:
        return
    from inventory.models import StockMovement

    if StockMovement.objects.filter(variant_id=variant.pk, reference='OPENING').exists():
        return
    StockMovement.objects.create(
        product=variant.product,
        variant=variant,
        movement_type='purchase',
        quantity=qty,
        unit_cost=variant.cost if variant.cost and variant.cost > 0 else None,
        reference='OPENING',
        notes='Opening stock when this size and colour was added',
    )


def sync_product_variant_combinations(
    product: Product,
    combinations: Sequence[Dict[str, Any]],
    *,
    apply_opening_stock: bool = True,
) -> List[ProductVariant]:
    """
    Create, keep, or remove variant rows so they match ``combinations`` exactly.

    A new row stores the price, cost, and MRP sent with that size and colour.
    Opening stock is stored only when ``apply_opening_stock`` is true, which
    is the first time the product is created. An edit leaves the count for
    the stock screens. Rows that already exist keep the amounts they have.

    Args:
        product: Parent product. Must have variants turned on.
        combinations: Rows from ``normalize_variant_combinations``. Empty
            removes every variant. A few hundred rows is the practical limit.
        apply_opening_stock: When true, a new size stores its opening count,
            0–1000000. When false, a new size starts at 0.

    Returns:
        The variant rows created in this call. Kept rows are not included.

    Raises:
        ValidationError: An opening count cannot be stored.
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
    by_pair = {(row.get('size'), row.get('color')): row for row in combinations}
    for size_id, color_id in wanted:
        if ProductVariant.objects.filter(
            product=product, size_id=size_id, color_id=color_id
        ).exists():
            continue
        size = Size.objects.filter(pk=size_id).first() if size_id else None
        color = Color.objects.filter(pk=color_id).first() if color_id else None
        variant = service._create_variant(product, size, color)
        combo = dict(by_pair.get((size_id, color_id), {}))
        if not apply_opening_stock:
            combo.pop('stock_quantity', None)
        _apply_new_variant_amounts(variant, combo)
        created.append(variant)

    if product.track_stock:
        sync_product_stock_from_variants(product)
        sync_product_cost_from_variants(product)
    return created
