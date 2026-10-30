"""
Repair trading-profit COGS after return-for-correction cycles.

Not only doubles: any qty change (3→2, 4→7, line remove) under the old unpost
path could leave surplus/shortfall sale drains on the live sale number, or leave
stale ``unit_cost`` stamps so reports still show the previous cost.

This tool:
  1. Soft-voids surplus live sale movements (retag ``#corrected-repair-…``)
     so kept drains match current cart qty per product.
  2. Flags shortfalls (movements fewer than cart) — those need admin-return →
     re-approve so stock/COGS drain at the corrected qty.
  3. Restamps ``unit_cost`` from kept movements / allocations / catalog when
     missing/zero, or when ``--force-restamp`` / surplus was cleared.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from django.db.models import Q
from django.utils import timezone

from inventory.models import StockMovement
from reports.trading_profit import _cogs_for_sales, _d
from sales.models import Sale, SaleItem
from sales.repair_sale_item_unit_cost import plan_unit_cost_repairs, apply_unit_cost_repairs


@dataclass(frozen=True)
class SurplusMovementRow:
    sale_number: str
    movement_id: int
    product_id: int
    product_name: str
    quantity: int
    total_cost: Decimal
    created_at: str


@dataclass
class SaleCogsAudit:
    sale_number: str
    status: str
    item_qty: int
    live_sale_mov_qty: int
    stamped_cogs: Decimal
    report_cogs: Decimal
    surplus_movements: list[SurplusMovementRow] = field(default_factory=list)
    duplicate_product_lines: list[tuple[int, Optional[int], int]] = field(default_factory=list)
    shortfall_qty: int = 0
    needs_recomplete: bool = False
    had_correction_trail: bool = False
    issues: list[str] = field(default_factory=list)


def _item_qty_by_product(sale: Sale) -> dict[int, int]:
    out: dict[int, int] = {}
    for item in sale.items.all():
        out[item.product_id] = out.get(item.product_id, 0) + int(item.quantity or 0)
    return out


def _has_correction_trail(sale_number: str) -> bool:
    if not sale_number:
        return False
    return StockMovement.objects.filter(
        movement_type='sale',
        reference__startswith=f'{sale_number}#corrected',
    ).exists()


def audit_sale_cogs(sale: Sale) -> SaleCogsAudit:
    item_qty_by_product = _item_qty_by_product(sale)
    item_qty = sum(item_qty_by_product.values())
    live = list(
        StockMovement.objects.filter(
            movement_type='sale',
            reference=sale.sale_number,
        ).select_related('product').order_by('-created_at', '-id')
    )
    live_qty = sum(int(m.quantity or 0) for m in live)
    stamped = Decimal('0')
    for item in sale.items.all():
        if item.unit_cost is not None and _d(item.unit_cost) > 0:
            stamped += _d(item.unit_cost) * _d(item.quantity)

    # Newest first. Keep whole chunks that fit remaining need; never keep a
    # chunk that would overshoot (that left COGS high after 3→1 style fixes).
    remaining_need: dict[int, int] = dict(item_qty_by_product)
    kept_qty: dict[int, int] = {pid: 0 for pid in item_qty_by_product}
    surplus: list[SurplusMovementRow] = []

    def _surplus_row(mov) -> SurplusMovementRow:
        return SurplusMovementRow(
            sale_number=sale.sale_number,
            movement_id=mov.id,
            product_id=mov.product_id,
            product_name=getattr(mov.product, 'name', None) or str(mov.product_id),
            quantity=int(mov.quantity or 0),
            total_cost=_d(mov.total_cost),
            created_at=mov.created_at.isoformat() if mov.created_at else '',
        )

    for mov in live:
        pid = mov.product_id
        need_left = remaining_need.get(pid, 0)
        qty = int(mov.quantity or 0)
        if need_left <= 0 or pid not in item_qty_by_product:
            surplus.append(_surplus_row(mov))
            continue
        if qty <= need_left:
            kept_qty[pid] = kept_qty.get(pid, 0) + qty
            remaining_need[pid] = need_left - qty
            continue
        # Too large for remaining need — soft-void; shortfall may remain.
        surplus.append(_surplus_row(mov))

    shortfall = sum(max(0, n) for n in remaining_need.values())

    line_keys: dict[tuple[int, Optional[int]], int] = {}
    for item in sale.items.all():
        key = (item.product_id, item.variant_id)
        line_keys[key] = line_keys.get(key, 0) + 1
    dups = [(pid, vid, n) for (pid, vid), n in line_keys.items() if n > 1]

    trail = _has_correction_trail(sale.sale_number)
    issues: list[str] = []
    if surplus:
        issues.append(
            f'surplus sale drains ({sum(r.quantity for r in surplus)} units) — soft-void'
        )
    if shortfall:
        issues.append(
            f'shortfall ({shortfall} units) — admin-return and re-approve to drain correct qty'
        )
    if dups:
        issues.append('duplicate product lines on cart — merge/remove then re-approve')
    if trail and not issues and sale.status == 'completed':
        # Prior correction with matching qty — still restamp if costs missing.
        missing_stamp = any(
            i.unit_cost is None or _d(i.unit_cost) <= 0 for i in sale.items.all()
        )
        if missing_stamp:
            issues.append('correction trail with missing unit_cost stamps — restamp')

    report_cogs = (
        _cogs_for_sales(Sale.objects.filter(pk=sale.pk))
        if sale.status == 'completed'
        else Decimal('0')
    )

    return SaleCogsAudit(
        sale_number=sale.sale_number,
        status=sale.status,
        item_qty=item_qty,
        live_sale_mov_qty=live_qty,
        stamped_cogs=stamped,
        report_cogs=report_cogs,
        surplus_movements=surplus,
        duplicate_product_lines=dups,
        shortfall_qty=shortfall,
        needs_recomplete=shortfall > 0 or bool(dups),
        had_correction_trail=trail,
        issues=issues,
    )


def find_inflated_cogs_sales(*, sale_numbers=None, limit: int = 200) -> list[SaleCogsAudit]:
    """Find completed sales with surplus, shortfall, duplicate lines, or correction trail gaps."""
    qs = Sale.objects.filter(status='completed').prefetch_related('items')
    if sale_numbers:
        qs = qs.filter(sale_number__in=sale_numbers)
    out: list[SaleCogsAudit] = []
    for sale in qs.order_by('-occurred_at', '-id')[: max(limit, 1) * 8]:
        audit = audit_sale_cogs(sale)
        if audit.issues:
            out.append(audit)
        if len(out) >= limit:
            break
    return out


def soft_void_surplus_movements(
    surplus: list[SurplusMovementRow],
    *,
    reason: str = 'repair COGS after correction',
) -> int:
    """Retag surplus sale drains so COGS movement fallback ignores them."""
    if not surplus:
        return 0
    tag = timezone.now().strftime('%Y%m%d%H%M%S')
    updated = 0
    for row in surplus:
        void_ref = f'{row.sale_number}#corrected-repair-{tag}-{row.movement_id}'
        changed = StockMovement.objects.filter(
            pk=row.movement_id,
            movement_type='sale',
            reference=row.sale_number,
        ).update(
            reference=void_ref,
            notes=f'{reason}: surplus/stale sale drain soft-voided',
        )
        updated += changed
    return updated


def _force_restamp_unit_costs(sale_numbers: list[str]) -> int:
    """
    Overwrite unit_cost from allocations → kept movements → catalog for every
    completed line on these sales (clears stale stamps after qty corrections).
    """
    items = list(
        SaleItem.objects.filter(
            sale__sale_number__in=sale_numbers,
            sale__status='completed',
        ).select_related('sale', 'product', 'variant')
    )
    if not items:
        return 0
    # plan_unit_cost_repairs skips positive stamps — temporarily clear then plan.
    SaleItem.objects.filter(id__in=[i.id for i in items]).update(unit_cost=None)
    refreshed = list(
        SaleItem.objects.filter(id__in=[i.id for i in items]).select_related(
            'sale', 'product', 'variant'
        )
    )
    plan = plan_unit_cost_repairs(refreshed)
    return apply_unit_cost_repairs(plan)


def repair_sale_cogs_double(
    *,
    sale_numbers: list[str],
    apply: bool = False,
    restamp_unit_cost: bool = True,
    force_restamp: bool = False,
) -> dict:
    """
    Audit and optionally repair one or more sales after correction qty changes.

    Returns a summary dict for the management command / callers.
    """
    sales = list(
        Sale.objects.filter(sale_number__in=sale_numbers).prefetch_related('items')
    )
    found = {s.sale_number for s in sales}
    missing = [n for n in sale_numbers if n not in found]
    audits = [audit_sale_cogs(s) for s in sales]
    all_surplus = [row for a in audits for row in a.surplus_movements]
    should_force = force_restamp or bool(all_surplus) or any(
        a.had_correction_trail for a in audits
    )

    voided = 0
    stamped = 0
    if apply:
        voided = soft_void_surplus_movements(all_surplus)
        if restamp_unit_cost:
            if should_force:
                stamped = _force_restamp_unit_costs(list(found))
            else:
                unresolved = list(
                    SaleItem.objects.filter(
                        sale__sale_number__in=sale_numbers,
                        sale__status='completed',
                    )
                    .filter(Q(unit_cost__isnull=True) | Q(unit_cost__lte=0))
                    .select_related('sale', 'product', 'variant')
                )
                plan = plan_unit_cost_repairs(unresolved)
                stamped = apply_unit_cost_repairs(plan)

        sales = list(
            Sale.objects.filter(sale_number__in=sale_numbers).prefetch_related('items')
        )
        audits = [audit_sale_cogs(s) for s in sales]

    return {
        'missing': missing,
        'audits': audits,
        'surplus_count': len(all_surplus),
        'voided': voided,
        'unit_costs_stamped': stamped,
        'applied': apply,
        'force_restamp': should_force,
    }
