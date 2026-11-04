"""
Sales-history PDF/Excel/CSV payload — products and sales first.

Customer identity is omitted from export rows; analysts get goods sold,
quantities, and ticket totals instead of a customer column.
"""

from django.db.models import Count, Prefetch, Sum
from django.db.models.functions import TruncDate

from sales.models import SaleItem

SALES_HISTORY_EXPORT_LIMIT = 10000


def build_sales_history_report(queryset, *, limit=None):
    """
    Build a product-forward sales history report for file export.

    Args:
        queryset: Filtered ``Sale`` queryset (same filters as the sales list).
        limit: Max sale tickets and sale lines in the file (1–SALES_HISTORY_EXPORT_LIMIT).
            Defaults to ``SALES_HISTORY_EXPORT_LIMIT``.

    Returns:
        Dict with ``summary``, ``by_product``, ``sale_lines``, slim ``sales``
        tickets (no customer), payment and daily breakdowns. Empty queryset
        yields zero totals and empty lists.
    """
    from reports.sales_goods import goods_sold_for_sales

    if limit is None:
        limit = SALES_HISTORY_EXPORT_LIMIT
    limit = max(1, min(int(limit), SALES_HISTORY_EXPORT_LIMIT))

    sales_count = queryset.count()
    total_revenue = queryset.aggregate(total=Sum('total'))['total'] or 0
    items_qs = SaleItem.objects.filter(sale__in=queryset)
    items_sold = items_qs.aggregate(qty=Sum('quantity'))['qty'] or 0

    by_payment = [
        {
            'payment_method': row['payment_method'] or 'unknown',
            'count': row['count'],
            'total': float(row['total'] or 0),
        }
        for row in queryset.values('payment_method')
        .annotate(count=Count('id'), total=Sum('total'))
        .order_by('payment_method')
    ]
    daily_breakdown = []
    for row in (
        queryset.annotate(day=TruncDate('occurred_at'))
        .values('day')
        .annotate(count=Count('id'), total=Sum('total'))
        .order_by('-day')
    ):
        day = row['day']
        daily_breakdown.append(
            {
                'day': day.isoformat() if day else None,
                'count': row['count'],
                'total': float(row['total'] or 0),
            }
        )

    goods = goods_sold_for_sales(
        queryset,
        line_limit=limit,
        items_qs=items_qs,
    )

    item_prefetch = Prefetch(
        'items',
        queryset=SaleItem.objects.select_related('product').order_by('id'),
    )
    sales_rows = []
    # Clear any prior `items` prefetch from the list view queryset.
    ticket_qs = (
        queryset.prefetch_related(None)
        .select_related('cashier')
        .prefetch_related(item_prefetch)
        .order_by('-occurred_at', '-id')[:limit]
    )
    for sale in ticket_qs:
        lines = list(sale.items.all())
        item_qty = sum(int(item.quantity or 0) for item in lines)
        product_bits = []
        for item in lines:
            name = getattr(item.product, 'name', None) or 'Item'
            qty = item.quantity
            product_bits.append(f'{name} × {qty}')
        when = sale.occurred_at or sale.created_at
        cashier = getattr(sale.cashier, 'username', None) or ''
        sales_rows.append(
            {
                'sale_number': sale.sale_number,
                'date': when,
                'cashier': cashier,
                'products': '; '.join(product_bits),
                'quantity': item_qty,
                'total': float(sale.total or 0),
                'payment': sale.payment_method or '',
                'status': sale.status or '',
            }
        )

    return {
        'summary': {
            'sales_count': sales_count,
            'total_revenue': float(total_revenue),
            'items_sold': int(items_sold or 0),
            'rows_in_file': len(sales_rows),
            'truncated': sales_count > limit,
        },
        'by_product': goods['by_product'],
        'sale_lines': goods['sale_lines'],
        'line_count': goods['line_count'],
        'lines_truncated': goods['lines_truncated'] or sales_count > limit,
        'by_payment_method': by_payment,
        'daily_breakdown': daily_breakdown,
        'sales': sales_rows,
    }
