"""Sales-history PDF/Excel/CSV payload (transaction list + totals)."""

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate

from sales.models import SaleItem

SALES_HISTORY_EXPORT_LIMIT = 2000


def build_sales_history_report(queryset, *, limit=SALES_HISTORY_EXPORT_LIMIT):
    """Summary + transaction rows for PDF/Excel/CSV of sales history."""
    sales_count = queryset.count()
    total_revenue = queryset.aggregate(total=Sum('total'))['total'] or 0
    items_sold = (
        SaleItem.objects.filter(sale__in=queryset).aggregate(qty=Sum('quantity'))['qty'] or 0
    )
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

    sales_rows = []
    for sale in queryset.order_by('-occurred_at', '-id')[:limit]:
        item_qty = sum(int(item.quantity or 0) for item in sale.items.all())
        when = sale.occurred_at or sale.created_at
        cashier = getattr(sale.cashier, 'username', None) or ''
        customer = getattr(sale.customer, 'name', None) or 'Walk-in'
        sales_rows.append(
            {
                'sale_number': sale.sale_number,
                'date': when,
                'cashier': cashier,
                'customer': customer,
                'items': item_qty,
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
        'by_payment_method': by_payment,
        'daily_breakdown': daily_breakdown,
        'sales': sales_rows,
    }
