"""Sales that have posted to stock, books, and reports.

Holding, pending-approval, and cancelled sales must not move totals.
"""

from sales.models import Sale, SaleItem

POSTED_SALE_STATUS = 'completed'


def posted_sales():
    return Sale.objects.filter(status=POSTED_SALE_STATUS)


def posted_sale_items():
    return SaleItem.objects.filter(sale__status=POSTED_SALE_STATUS)
