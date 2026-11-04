"""
Goods-sold aggregations for sales / sales-overview reports and Excel export.

Builds product-level quantity and revenue (plus stamped COGS when present) so
exports are not limited to payment-method or daily sale *counts*.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce

from reports.sale_scope import posted_sale_items


_DEC = DecimalField(max_digits=14, decimal_places=2)
_ZERO = Value(Decimal('0.00'), output_field=_DEC)


def goods_sold_for_sales(
    sales_qs,
    *,
    line_limit: int = 5_000,
    items_qs=None,
) -> dict[str, Any]:
    """
    Aggregate goods sold for a sale queryset.

    Args:
        sales_qs: ``Sale`` queryset already scoped to the report period/filters.
        line_limit: Max individual sale-line rows for the detail sheet
            (1–20_000). Product roll-up is never truncated.
        items_qs: Optional ``SaleItem`` queryset; when omitted, uses posted
            (completed) sale lines under ``sales_qs``.

    Returns:
        Dict with:
        - ``by_product``: product name/sku, quantity, revenue, cogs, margin
        - ``sale_lines``: up to ``line_limit`` lines (sale number, product, qty…)
        - ``lines_truncated``: True when more lines exist than ``line_limit``
        - ``line_count``: total matching sale lines
    """
    limit = max(1, min(int(line_limit or 5_000), 20_000))
    if items_qs is not None:
        items = items_qs
    else:
        items = posted_sale_items().filter(sale__in=sales_qs.values('pk'))

    cogs_expr = ExpressionWrapper(
        F('quantity') * Coalesce(F('unit_cost'), _ZERO),
        output_field=_DEC,
    )
    by_product_qs = (
        items.values(
            'product__name',
            'product__sku',
            'product__category__name',
        )
        .annotate(
            quantity_sold=Sum('quantity'),
            revenue=Sum('subtotal'),
            cogs=Sum(cogs_expr),
            sale_line_count=Count('id'),
        )
        .order_by('-revenue')
    )

    by_product = []
    for row in by_product_qs:
        qty = float(row['quantity_sold'] or 0)
        revenue = float(row['revenue'] or 0)
        cogs = float(row['cogs'] or 0)
        gp = revenue - cogs
        margin = round(gp / revenue * 100, 2) if revenue else None
        by_product.append(
            {
                'product': row['product__name'] or 'Item',
                'sku': row['product__sku'] or '',
                'category': row['product__category__name'] or '',
                'quantity_sold': qty,
                'revenue': revenue,
                'cogs': cogs,
                'gross_profit': round(gp, 2),
                'margin_pct': margin,
                'sale_line_count': int(row['sale_line_count'] or 0),
            }
        )

    line_count = items.count()
    line_rows = list(
        items.select_related('product', 'sale')
        .order_by('-sale__occurred_at', 'sale_id', 'id')[:limit]
        .values(
            'sale__sale_number',
            'sale__occurred_at',
            'product__name',
            'product__sku',
            'quantity',
            'unit_price',
            'subtotal',
            'unit_cost',
        )
    )
    sale_lines = []
    for row in line_rows:
        qty = float(row['quantity'] or 0)
        unit_price = float(row['unit_price'] or 0)
        line_sale = float(row['subtotal'] or 0)
        unit_cost = (
            float(row['unit_cost'])
            if row['unit_cost'] is not None
            else None
        )
        line_cogs = round(qty * float(unit_cost or 0), 2)
        occurred = row['sale__occurred_at']
        sale_lines.append(
            {
                'sale_number': row['sale__sale_number'] or '',
                'sale_date': occurred.isoformat() if occurred else None,
                'product': row['product__name'] or 'Item',
                'sku': row['product__sku'] or '',
                'quantity': qty,
                'unit_price': unit_price,
                'line_sale': line_sale,
                'unit_cost': unit_cost,
                'line_cogs': line_cogs,
                'line_gross_profit': round(line_sale - line_cogs, 2),
            }
        )

    return {
        'by_product': by_product,
        'sale_lines': sale_lines,
        'line_count': line_count,
        'lines_truncated': line_count > limit,
    }
