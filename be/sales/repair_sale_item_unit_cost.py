"""
One-shot alignment: stamp SaleItem.unit_cost when it is null/0 using the same
fallback order as trading-profit COGS (layer allocations → stock movements →
catalog). Cleared stamped costs stop the "stock-movement cost" warning.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional

from django.db.models import Q, Sum
from django.utils import timezone

from inventory.models import StockMovement
from products.stock_utils import sellable_unit_cost
from sales.models import SaleItem, SaleItemLayerAllocation


def _d(value) -> Decimal:
    return Decimal(str(value or 0))


def _unit_cost_missing(unit_cost) -> bool:
    if unit_cost is None:
        return True
    return _d(unit_cost) <= 0


@dataclass(frozen=True)
class UnitCostRepairRow:
    sale_item_id: int
    sale_number: str
    product_name: str
    quantity: Decimal
    old_unit_cost: Optional[Decimal]
    new_unit_cost: Decimal
    source: str  # layer_allocation | stock_movement | catalog


def unresolved_sale_items(*, sale_numbers=None, date_from=None, date_to=None):
    """Completed sale lines with missing stamped unit cost."""
    qs = (
        SaleItem.objects.filter(
            sale__status='completed',
        )
        .filter(Q(unit_cost__isnull=True) | Q(unit_cost__lte=0))
        .select_related('sale', 'product', 'variant')
        .order_by('sale_id', 'id')
    )
    if sale_numbers:
        qs = qs.filter(sale__sale_number__in=sale_numbers)
    if date_from is not None:
        qs = qs.filter(sale__occurred_at__gte=date_from)
    if date_to is not None:
        qs = qs.filter(sale__occurred_at__lte=date_to)
    return qs


def plan_unit_cost_repairs(
    items: Iterable[SaleItem],
) -> list[UnitCostRepairRow]:
    """
    Resolve a stamped unit_cost for each missing line without writing.

    Prefer allocation / movement sources so historical books match what the
    trading-profit report already shows; catalog is last resort.
    """
    items = list(items)
    if not items:
        return []

    item_ids = [item.id for item in items]
    alloc_totals: dict[int, Decimal] = {}
    for alloc in SaleItemLayerAllocation.objects.filter(
        sale_item_id__in=item_ids,
        unit_cost__gt=0,
    ).only('sale_item_id', 'quantity', 'unit_cost'):
        alloc_totals[alloc.sale_item_id] = alloc_totals.get(
            alloc.sale_item_id, Decimal('0')
        ) + (_d(alloc.quantity) * _d(alloc.unit_cost))

    refs = {item.sale.sale_number for item in items if item.sale.sale_number}
    mov_by_ref_product: dict[tuple[str, int], Decimal] = {
        (row['reference'], row['product_id']): _d(row['total'])
        for row in (
            StockMovement.objects.filter(movement_type='sale', reference__in=refs)
            .values('reference', 'product_id')
            .annotate(total=Sum('total_cost'))
        )
    }

    # Unresolved qty per (sale_number, product) for splitting movement totals.
    unresolved_qty: dict[tuple[str, int], Decimal] = {}
    for item in items:
        if item.id in alloc_totals:
            continue
        key = (item.sale.sale_number, item.product_id)
        unresolved_qty[key] = unresolved_qty.get(key, Decimal('0')) + _d(item.quantity)

    repairs: list[UnitCostRepairRow] = []
    for item in items:
        qty = _d(item.quantity)
        if qty <= 0:
            continue
        sale_number = item.sale.sale_number or ''
        product_name = getattr(item.product, 'name', None) or 'Item'
        old = None if item.unit_cost is None else _d(item.unit_cost)

        if item.id in alloc_totals and alloc_totals[item.id] > 0:
            line_cogs = alloc_totals[item.id]
            new_uc = (line_cogs / qty).quantize(Decimal('0.0001'))
            source = 'layer_allocation'
        else:
            mov_total = mov_by_ref_product.get((sale_number, item.product_id), Decimal('0'))
            uqty = unresolved_qty.get((sale_number, item.product_id), Decimal('0'))
            if mov_total > 0 and uqty > 0:
                line_cogs = (mov_total * qty / uqty).quantize(Decimal('0.01'))
                new_uc = (line_cogs / qty).quantize(Decimal('0.0001'))
                source = 'stock_movement'
            else:
                catalog = sellable_unit_cost(item.product, item.variant)
                if catalog is None or _d(catalog) <= 0:
                    continue
                new_uc = _d(catalog).quantize(Decimal('0.0001'))
                source = 'catalog'

        if new_uc <= 0:
            continue
        repairs.append(
            UnitCostRepairRow(
                sale_item_id=item.id,
                sale_number=sale_number,
                product_name=product_name,
                quantity=qty,
                old_unit_cost=old,
                new_unit_cost=new_uc,
                source=source,
            )
        )
    return repairs


def apply_unit_cost_repairs(repairs: Iterable[UnitCostRepairRow]) -> int:
    """Write planned unit_cost stamps. Returns number of rows updated."""
    updated = 0
    for row in repairs:
        changed = SaleItem.objects.filter(
            pk=row.sale_item_id,
        ).filter(
            Q(unit_cost__isnull=True) | Q(unit_cost__lte=0)
        ).update(unit_cost=row.new_unit_cost)
        updated += changed
    return updated


def repair_unit_costs(
    *,
    sale_numbers=None,
    date_from=None,
    date_to=None,
    apply: bool = False,
) -> tuple[list[UnitCostRepairRow], int]:
    """
    Plan (and optionally apply) unit_cost stamps for completed sales.

    Returns (planned_rows, applied_count).
    """
    items = list(
        unresolved_sale_items(
            sale_numbers=sale_numbers,
            date_from=date_from,
            date_to=date_to,
        )
    )
    repairs = plan_unit_cost_repairs(items)
    applied = apply_unit_cost_repairs(repairs) if apply else 0
    return repairs, applied


def day_start(raw: str):
    from datetime import datetime, time

    day = datetime.strptime(raw, '%Y-%m-%d').date()
    return timezone.make_aware(datetime.combine(day, time.min))


def day_end(raw: str):
    from datetime import datetime, time

    day = datetime.strptime(raw, '%Y-%m-%d').date()
    return timezone.make_aware(datetime.combine(day, time.max))
