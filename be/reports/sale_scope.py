"""Sales that have posted to stock, books, and reports.

Holding, pending-approval, and cancelled sales must not move totals.
"""

from sales.models import Sale, SaleItem

POSTED_SALE_STATUS = 'completed'


def posted_sales():
    return Sale.objects.filter(status=POSTED_SALE_STATUS)


def posted_sale_items():
    return SaleItem.objects.filter(sale__status=POSTED_SALE_STATUS)


def items_sold(sales_qs) -> int:
    """Units sold across ``sales_qs``, summed apart so sale totals are not repeated per line."""
    from django.db.models import Sum

    total = SaleItem.objects.filter(sale__in=sales_qs.values('pk')).aggregate(
        total=Sum('quantity')
    )['total']
    return int(total or 0)
