"""
Overwrite SaleItem.unit_cost stamps with the product/variant's current catalog cost.

Use once after cleaning catalog COST values so Trading profit COGS matches the
Products list. New sales keep using FIFO stamps going forward.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List, Optional, Sequence

from django.db import transaction
from django.utils import timezone

from products.stock_utils import sellable_unit_cost
from sales.models import SaleItem


def _d(value) -> Decimal:
    """
    Coerce to Decimal.

    Args:
        value: Number, string, or None.

    Returns:
        Decimal; None/blank → Decimal('0').
    """
    if value is None or value == '':
        return Decimal('0')
    return Decimal(str(value))


def day_start(raw: str):
    """
    Inclusive start of a calendar day in the active timezone.

    Args:
        raw: YYYY-MM-DD string.

    Returns:
        Aware datetime at local midnight.

    Raises:
        ValueError: When ``raw`` is not YYYY-MM-DD.
    """
    from datetime import datetime, time

    day = datetime.strptime(raw, '%Y-%m-%d').date()
    return timezone.make_aware(datetime.combine(day, time.min))


def day_end(raw: str):
    """
    Inclusive end of a calendar day in the active timezone.

    Args:
        raw: YYYY-MM-DD string.

    Returns:
        Aware datetime at local end-of-day.

    Raises:
        ValueError: When ``raw`` is not YYYY-MM-DD.
    """
    from datetime import datetime, time

    day = datetime.strptime(raw, '%Y-%m-%d').date()
    return timezone.make_aware(datetime.combine(day, time.max))


@dataclass(frozen=True)
class CatalogCostRectifyRow:
    """One sale line that would / did change to catalog cost."""

    sale_item_id: int
    sale_number: str
    product_name: str
    variant_label: str
    quantity: Decimal
    old_unit_cost: Optional[Decimal]
    new_unit_cost: Decimal


def catalog_cost_for_item(item: SaleItem) -> Decimal:
    """
    Current catalog unit cost for a sale line (variant first, else product rules).

    Args:
        item: SaleItem with product/variant preferably select_related.

    Returns:
        Catalog cost ≥ 0, quantized to 0.01. Zero when unset.
    """
    product = item.product
    variant = item.variant
    if product is None:
        return Decimal('0.00')
    cost = sellable_unit_cost(product, variant)
    return _d(cost).quantize(Decimal('0.01'))


def completed_sale_items(
    *,
    sale_numbers: Optional[Sequence[str]] = None,
    date_from=None,
    date_to=None,
):
    """
    Completed sale lines in optional sale-number / occurred_at window.

    Args:
        sale_numbers: Optional list of sale_number strings (exact match).
        date_from: Inclusive occurred_at lower bound (datetime or None).
        date_to: Inclusive occurred_at upper bound (datetime or None).

    Returns:
        QuerySet of SaleItem ordered by sale_id, id (may be empty).
    """
    qs = (
        SaleItem.objects.filter(sale__status='completed')
        .select_related('sale', 'product', 'variant', 'variant__size', 'variant__color')
        .order_by('sale_id', 'id')
    )
    if sale_numbers:
        qs = qs.filter(sale__sale_number__in=list(sale_numbers))
    if date_from is not None:
        qs = qs.filter(sale__occurred_at__gte=date_from)
    if date_to is not None:
        qs = qs.filter(sale__occurred_at__lte=date_to)
    return qs


def plan_catalog_cost_rectify(
    items: Iterable[SaleItem],
) -> List[CatalogCostRectifyRow]:
    """
    Build rows where stamped unit_cost differs from current catalog cost.

    Skips lines with catalog cost ≤ 0 (nothing trustworthy to write) and lines
    already matching catalog (within 0.01).

    Args:
        items: SaleItem iterable (product/variant loaded).

    Returns:
        List of planned changes (0–N; N ≤ number of items).
    """
    rows: List[CatalogCostRectifyRow] = []
    for item in items:
        new_uc = catalog_cost_for_item(item)
        if new_uc <= 0:
            continue
        old = None if item.unit_cost is None else _d(item.unit_cost).quantize(Decimal('0.01'))
        if old is not None and old == new_uc:
            continue
        variant = item.variant
        variant_label = ''
        if variant is not None:
            size = getattr(getattr(variant, 'size', None), 'name', None) or ''
            color = getattr(getattr(variant, 'color', None), 'name', None) or ''
            variant_label = ' / '.join(b for b in (size, color) if b)
        rows.append(
            CatalogCostRectifyRow(
                sale_item_id=item.id,
                sale_number=item.sale.sale_number or '',
                product_name=getattr(item.product, 'name', None) or 'Item',
                variant_label=variant_label,
                quantity=_d(item.quantity),
                old_unit_cost=old,
                new_unit_cost=new_uc,
            )
        )
    return rows


@transaction.atomic
def apply_catalog_cost_rectify(rows: Sequence[CatalogCostRectifyRow]) -> int:
    """
    Write planned catalog costs onto SaleItem.unit_cost.

    Args:
        rows: Output of ``plan_catalog_cost_rectify`` (may be empty).

    Returns:
        Number of SaleItem rows updated (0–len(rows)).

    Side effects:
        Updates ``SaleItem.unit_cost`` only. Does not change stock, layers,
        payments, or audit logs. Trading profit COGS will use the new stamps.
    """
    if not rows:
        return 0
    updated = 0
    for row in rows:
        n = SaleItem.objects.filter(pk=row.sale_item_id).update(
            unit_cost=row.new_unit_cost
        )
        updated += int(n)
    return updated


def rectify_sale_costs_to_catalog(
    *,
    sale_numbers: Optional[Sequence[str]] = None,
    date_from=None,
    date_to=None,
    apply: bool = False,
) -> tuple[list[CatalogCostRectifyRow], int]:
    """
    Plan (and optionally apply) catalog cost stamps on completed sale lines.

    Args:
        sale_numbers: Optional sale_number filter.
        date_from: Optional inclusive occurred_at start.
        date_to: Optional inclusive occurred_at end.
        apply: When True, write stamps; when False, dry-run only.

    Returns:
        ``(planned_rows, applied_count)``. ``applied_count`` is 0 on dry-run.
    """
    items = completed_sale_items(
        sale_numbers=sale_numbers,
        date_from=date_from,
        date_to=date_to,
    )
    planned = plan_catalog_cost_rectify(items)
    if not apply:
        return planned, 0
    return planned, apply_catalog_cost_rectify(planned)
