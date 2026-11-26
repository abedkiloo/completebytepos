"""
Per-SKU profitability ranking for product reports.

Builds quantity, revenue, COGS, gross profit, average gross profit per unit,
and margin % from stamped sale-line costs, then ranks by the requested sort
key so managers can see which goods contribute the most profit.
"""

from __future__ import annotations

from typing import Any, Iterable

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce

VALID_SORTS = frozenset({
    'revenue',
    'quantity',
    'gross_profit',
    'avg_gross_profit',
    'margin_pct',
})
DEFAULT_SORT = 'revenue'


def normalize_product_sort(raw: str | None, *, default: str = DEFAULT_SORT) -> str:
    """
    Normalize a product ranking sort key.

    Args:
        raw: Query ``sort`` value (any string or None). Max practical length ~32.
        default: Fallback when raw is empty/unknown. One of VALID_SORTS.

    Returns:
        One of ``revenue``, ``quantity``, ``gross_profit``, ``avg_gross_profit``,
        ``margin_pct``.
    """
    key = (raw or '').strip().lower()
    if key in ('qty', 'units', 'quantity_sold'):
        key = 'quantity'
    if key in ('profit', 'gp', 'gross'):
        key = 'gross_profit'
    if key in (
        'avg_profit',
        'avg_gp',
        'average_gross_profit',
        'avg_gross',
        'unit_profit',
        'profit_per_unit',
    ):
        key = 'avg_gross_profit'
    if key in ('margin', 'margin_percent', 'margin%'):
        key = 'margin_pct'
    if key in VALID_SORTS:
        return key
    return default if default in VALID_SORTS else DEFAULT_SORT


def margin_pct(revenue: float, cogs: float) -> float | None:
    """
    Gross margin percent: (revenue − cogs) / revenue × 100.

    Args:
        revenue: Line revenue total (≥ 0 typical).
        cogs: Cost of goods sold for the same lines (≥ 0 typical).

    Returns:
        Rounded percent to 2 dp, or None when revenue is 0.
    """
    if not revenue:
        return None
    return round((revenue - cogs) / revenue * 100.0, 2)


def annotate_product_sales(queryset):
    """
    Aggregate sale items per product with COGS from stamped unit_cost.

    Args:
        queryset: ``SaleItem`` queryset already scoped to posted sales/dates.

    Returns:
        Values queryset annotated with quantity_sold, revenue, avg_price, cogs,
        line_count.
    """
    _dec = DecimalField(max_digits=14, decimal_places=2)
    _zero = Value(0, output_field=_dec)
    cogs_expr = ExpressionWrapper(
        F('quantity') * Coalesce(F('unit_cost'), _zero),
        output_field=_dec,
    )
    return queryset.values(
        'product__id',
        'product__name',
        'product__sku',
        'product__category__name',
    ).annotate(
        quantity_sold=Sum('quantity'),
        revenue=Sum('subtotal'),
        avg_price=Sum('subtotal') / Sum('quantity'),
        cogs=Sum(cogs_expr),
        line_count=Count('id'),
    )


def row_from_aggregate(row: dict[str, Any], *, hub_keys: bool = False) -> dict[str, Any]:
    """
    Map one annotated product aggregate to a report row with margin.

    Args:
        row: Values-annotate dict from ``annotate_product_sales``.
        hub_keys: When True, use hub/top_products field names
            (``product_id``, ``name``, …).

    Returns:
        Dict with quantity, revenue, cogs, gross_profit, avg_gross_profit
        (GP per unit sold), margin_pct (0–100 or None).
    """
    qty = float(row.get('quantity_sold') or 0)
    revenue = float(row.get('revenue') or 0)
    cogs = float(row.get('cogs') or 0)
    gp = round(revenue - cogs, 2)
    margin = margin_pct(revenue, cogs)
    avg_unit_cost = round(cogs / qty, 4) if qty else None
    # Average gross profit per unit sold — compares SKUs on profit density.
    avg_gross_profit = round(gp / qty, 4) if qty else None
    if hub_keys:
        return {
            'product_id': row.get('product__id'),
            'name': row.get('product__name') or '(unnamed product)',
            'sku': row.get('product__sku') or '',
            'category': row.get('product__category__name') or 'Uncategorised',
            'quantity_sold': int(qty) if qty == int(qty) else qty,
            'revenue': revenue,
            'line_count': int(row.get('line_count') or 0),
            'cogs': cogs,
            'avg_unit_cost': avg_unit_cost,
            'gross_profit': gp,
            'avg_gross_profit': avg_gross_profit,
            'margin_pct': margin,
        }
    return {
        'product__id': row.get('product__id'),
        'product__name': row.get('product__name'),
        'product__sku': row.get('product__sku'),
        'product__category__name': row.get('product__category__name'),
        'quantity_sold': row.get('quantity_sold'),
        'revenue': row.get('revenue'),
        'avg_price': row.get('avg_price'),
        'cogs': cogs,
        'avg_unit_cost': avg_unit_cost,
        'gross_profit': gp,
        'avg_gross_profit': avg_gross_profit,
        'margin_pct': margin,
        'line_count': int(row.get('line_count') or 0),
    }


def sort_product_rows(
    rows: Iterable[dict[str, Any]],
    sort: str,
    *,
    descending: bool = True,
) -> list[dict[str, Any]]:
    """
    Rank product rows by revenue, units, gross profit, avg GP/unit, or margin %.

    Args:
        rows: Product profitability rows (iterable, 0–100_000 typical).
        sort: Normalized sort key from ``normalize_product_sort``.
        descending: Highest-first when True (default for “which earns more”).

    Returns:
        New sorted list. Margin / avg GP None sorts last when descending.
    """
    key = normalize_product_sort(sort)

    def sort_value(row: dict[str, Any]):
        if key == 'quantity':
            return float(row.get('quantity_sold') or 0)
        if key == 'gross_profit':
            return float(row.get('gross_profit') or 0)
        if key == 'avg_gross_profit':
            avg = row.get('avg_gross_profit')
            if avg is None:
                return float('-inf') if descending else float('inf')
            return float(avg)
        if key == 'margin_pct':
            m = row.get('margin_pct')
            if m is None:
                return float('-inf') if descending else float('inf')
            return float(m)
        return float(row.get('revenue') or 0)

    return sorted(rows, key=sort_value, reverse=descending)


def build_product_profitability_rows(
    queryset,
    *,
    sort: str = DEFAULT_SORT,
    limit: int | None = None,
    hub_keys: bool = False,
) -> tuple[list[dict[str, Any]], str]:
    """
    Aggregate, attach margins, rank, and optionally truncate.

    Args:
        queryset: Scoped ``SaleItem`` queryset.
        sort: Ranking key (revenue / quantity / gross_profit /
            avg_gross_profit / margin_pct).
        limit: When set (1–50 typical), return only the top N after sort.
        hub_keys: Use top_products field naming.

    Returns:
        ``(rows, sort_key)`` where rows length is 0..N (or all when limit None).
    """
    sort_key = normalize_product_sort(sort)
    raw = list(annotate_product_sales(queryset))
    rows = [row_from_aggregate(r, hub_keys=hub_keys) for r in raw]
    ranked = sort_product_rows(rows, sort_key)
    if limit is not None:
        try:
            n = max(0, int(limit))
        except (TypeError, ValueError):
            n = 0
        ranked = ranked[:n]
    return ranked, sort_key
