"""On-demand totals for Sales history filters (full range, not one page)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from sales.models import Sale
from sales.services import SaleService


def _payment_method_label(code: Optional[str]) -> str:
    """
    Human label for a Sale.payment_method code.

    Args:
        code: Stored payment method string, or None/blank.

    Returns:
        Display label from Sale.PAYMENT_METHODS, or the raw code, or ``Other``.
        Empty/None codes map to ``Other``.
    """
    key = (code or '').strip()
    if not key:
        return 'Other'
    for value, label in Sale.PAYMENT_METHODS:
        if value == key:
            return str(label)
    return key


def summarize_sales_history(
    *,
    filters: Optional[Dict[str, Any]] = None,
    request=None,
) -> Dict[str, Any]:
    """
    Aggregate sale totals for the same filters as the Sales history list.

    Uses ``SaleService.build_queryset`` so date/status/cashier/payment/search
    and visibility rules match the paginated list. Aggregates over all matching
    rows (not one page). Requires both ``date_from`` and ``date_to`` so admins
    always calculate a specified period.

    Args:
        filters: Same keys as list (date_from, date_to, status, payment_method,
            search, cashier_id, branch_id, show_all). Both date_from and date_to
            required (YYYY-MM-DD). Empty filters raise ValueError.
        request: HttpRequest for branch + own-sales visibility (may be None in tests).

    Returns:
        Dict with:
        - count (int ≥ 0): matching sales
        - total_amount (str): sum of sale.total
        - total_paid (str): sum of sale.amount_paid
        - by_method (list): {payment_method, payment_method_label, count, total}
        - date_from / date_to (str): echoed period

    Raises:
        ValueError: When date_from or date_to is missing/blank.
    """
    filters = dict(filters or {})
    date_from = (filters.get('date_from') or '').strip()
    date_to = (filters.get('date_to') or '').strip()
    if not date_from or not date_to:
        raise ValueError('Choose a From and To date before calculating the total.')

    filters['date_from'] = date_from
    filters['date_to'] = date_to

    service = SaleService()
    filtered = service.build_queryset(filters, request=request).order_by().values('id').distinct()
    base = Sale.objects.filter(id__in=filtered)

    totals = base.aggregate(
        count=Count('id'),
        total_amount=Coalesce(Sum('total'), Decimal('0')),
        total_paid=Coalesce(Sum('amount_paid'), Decimal('0')),
    )
    by_method_rows = (
        base.values('payment_method')
        .annotate(
            count=Count('id'),
            total=Coalesce(Sum('total'), Decimal('0')),
        )
        .order_by('payment_method')
    )
    by_method = [
        {
            'payment_method': row['payment_method'] or 'other',
            'payment_method_label': _payment_method_label(row['payment_method']),
            'count': int(row['count'] or 0),
            'total': str(row['total'] or Decimal('0')),
        }
        for row in by_method_rows
    ]

    return {
        'count': int(totals['count'] or 0),
        'total_amount': str(totals['total_amount'] or Decimal('0')),
        'total_paid': str(totals['total_paid'] or Decimal('0')),
        'by_method': by_method,
        'date_from': date_from,
        'date_to': date_to,
    }
