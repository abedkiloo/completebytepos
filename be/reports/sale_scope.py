"""
Posted-sale scope for reports and dashboards.

Public entry points:
    - ``posted_sales`` / ``posted_sale_items`` — ORM filters for ``status=completed``
    - ``items_sold`` — unit count across a sale queryset

Holding, pending-approval, and cancelled sales must not move totals. Read-only;
no audit or stock side effects.
"""

from sales.models import Sale, SaleItem

POSTED_SALE_STATUS = 'completed'


def posted_sales():
    """
    Return sales that have posted to stock, books, and reports.

    Returns:
        A ``Sale`` queryset filtered to ``status=completed`` only.
    """
    return Sale.objects.filter(status=POSTED_SALE_STATUS)


def posted_sale_items():
    """
    Return line items belonging to posted (completed) sales.

    Returns:
        A ``SaleItem`` queryset joined to sales with ``status=completed``.
    """
    return SaleItem.objects.filter(sale__status=POSTED_SALE_STATUS)


def items_sold(sales_qs) -> int:
    """
    Sum unit quantities sold across a sale queryset.

    Aggregates ``SaleItem.quantity`` for all items whose parent sale is in
    ``sales_qs``. Sale-level totals are not double-counted when a sale has
    multiple lines.

    Args:
        sales_qs: ``Sale`` queryset or any iterable resolvable via ``values('pk')``.
            Empty queryset yields ``0``.

    Returns:
        Total units sold as a non-negative integer (``0`` when no lines or null sum).
    """
    from django.db.models import Sum

    total = SaleItem.objects.filter(sale__in=sales_qs.values('pk')).aggregate(
        total=Sum('quantity')
    )['total']
    return int(total or 0)
