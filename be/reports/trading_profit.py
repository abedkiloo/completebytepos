"""Trading profit for week / month / year (net sales − COGS − expenses + income)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import ExpressionWrapper, F, Sum, fields as dj_fields
from django.utils import timezone
from expenses.models import Expense
from income.models import Income
from inventory.models import StockMovement
from reports.sale_scope import posted_sales
from sales.models import SaleItem, SaleRefund, SaleRefundItem


def _d(value) -> Decimal:
    return Decimal(str(value or 0))


def _money(value) -> float:
    return float(_d(value).quantize(Decimal('0.01')))


def _cogs_for_sales(sales_qs) -> Decimal:
    """FIFO-stamped line cost, with legacy sale-movement fallback."""
    sale_items = SaleItem.objects.filter(sale__in=sales_qs)
    with_cost = sale_items.filter(unit_cost__isnull=False).aggregate(
        total=Sum(
            ExpressionWrapper(
                F('quantity') * F('unit_cost'),
                output_field=dj_fields.DecimalField(max_digits=14, decimal_places=2),
            )
        )
    )['total']
    legacy_numbers = list(
        sale_items.filter(unit_cost__isnull=True).values_list('sale__sale_number', flat=True)
    )
    legacy = Decimal('0')
    if legacy_numbers:
        legacy = _d(
            StockMovement.objects.filter(
                movement_type='sale',
                reference__in=legacy_numbers,
            ).aggregate(total=Sum('total_cost'))['total']
        )
    return _d(with_cost) + legacy


def _refund_cogs(refund_qs) -> Decimal:
    """Cost restored when items are voided/refunded (sale_item.unit_cost × qty)."""
    rows = (
        SaleRefundItem.objects.filter(refund__in=refund_qs)
        .select_related('sale_item')
        .only('quantity', 'sale_item__unit_cost')
    )
    total = Decimal('0')
    for row in rows:
        cost = getattr(row.sale_item, 'unit_cost', None)
        if cost is None:
            continue
        total += _d(cost) * _d(row.quantity)
    return total


def compute_trading_profit(*, start, end) -> dict[str, Any]:
    """
    Net profit = (gross sales − refunds) − (COGS − refund COGS) − expenses + other income.

    Revenue uses Sale.total (tax-inclusive). ``tax_amount`` is returned for visibility only.
    """
    sales_qs = posted_sales()
    if start is not None:
        sales_qs = sales_qs.filter(occurred_at__gte=start)
    if end is not None:
        sales_qs = sales_qs.filter(occurred_at__lte=end)

    sales_agg = sales_qs.aggregate(
        gross_sales=Sum('total'),
        tax_amount=Sum('tax_amount'),
        discount_amount=Sum('discount_amount'),
    )
    sale_count = sales_qs.count()
    gross_sales = _d(sales_agg['gross_sales'])
    tax_amount = _d(sales_agg['tax_amount'])
    discount_amount = _d(sales_agg['discount_amount'])

    refund_qs = SaleRefund.objects.filter(sale__status='completed')
    if start is not None:
        refund_qs = refund_qs.filter(created_at__gte=start)
    if end is not None:
        refund_qs = refund_qs.filter(created_at__lte=end)
    refunds_total = _d(refund_qs.aggregate(total=Sum('amount'))['total'])
    refund_count = refund_qs.count()

    net_sales = gross_sales - refunds_total
    cogs_sold = _cogs_for_sales(sales_qs)
    cogs_refunded = _refund_cogs(refund_qs)
    cogs = cogs_sold - cogs_refunded
    if cogs < 0:
        cogs = Decimal('0')

    expenses_qs = Expense.objects.filter(status='approved')
    if start is not None:
        expenses_qs = expenses_qs.filter(
            expense_date__gte=start.date() if hasattr(start, 'date') else start
        )
    if end is not None:
        expenses_qs = expenses_qs.filter(
            expense_date__lte=end.date() if hasattr(end, 'date') else end
        )
    expenses_total = _d(expenses_qs.aggregate(total=Sum('amount'))['total'])

    income_qs = Income.objects.filter(status='approved')
    if start is not None:
        income_qs = income_qs.filter(
            income_date__gte=start.date() if hasattr(start, 'date') else start
        )
    if end is not None:
        income_qs = income_qs.filter(
            income_date__lte=end.date() if hasattr(end, 'date') else end
        )
    other_income = _d(income_qs.aggregate(total=Sum('amount'))['total'])

    # Purchases for visibility only — not in net profit.
    purchases_qs = StockMovement.objects.filter(movement_type='purchase')
    if start is not None:
        purchases_qs = purchases_qs.filter(created_at__gte=start)
    if end is not None:
        purchases_qs = purchases_qs.filter(created_at__lte=end)
    purchases_total = _d(purchases_qs.aggregate(total=Sum('total_cost'))['total'])

    gross_profit = net_sales - cogs
    net_profit = gross_profit - expenses_total + other_income
    margin = float(net_profit / net_sales * 100) if net_sales > 0 else 0.0

    return {
        'basis': 'trading',
        'formula': 'net_sales - cogs - expenses + other_income',
        'gross_sales': _money(gross_sales),
        'refunds': _money(refunds_total),
        'net_sales': _money(net_sales),
        'tax_amount': _money(tax_amount),
        'discount_amount': _money(discount_amount),
        'cogs': _money(cogs),
        'cogs_sold': _money(cogs_sold),
        'cogs_refunded': _money(cogs_refunded),
        'gross_profit': _money(gross_profit),
        'expenses': _money(expenses_total),
        'other_income': _money(other_income),
        'purchases': _money(purchases_total),
        'net_profit': _money(net_profit),
        'profit_margin': round(margin, 2),
        'sale_count': sale_count,
        'refund_count': refund_count,
    }


def trading_profit_for_request(request) -> dict[str, Any]:
    from reports.services import resolve_period

    params = getattr(request, 'query_params', request.GET)
    period = (params.get('period') or '').lower().strip()
    if not period and not params.get('date_from'):
        # Default: month-to-date
        class _Req:
            query_params = {'period': 'month'}
            GET = query_params

        start, end, label = resolve_period(_Req())
        period = 'month'
    else:
        start, end, label = resolve_period(request)
        if not period:
            period = label or 'custom'

    if end is None:
        end = timezone.now()

    summary = compute_trading_profit(start=start, end=end)
    return {
        'period': period if period in ('week', 'month', 'year', 'today') else (label or 'custom'),
        'date_from': start.isoformat() if start else None,
        'date_to': end.isoformat() if end else None,
        'summary': summary,
    }
