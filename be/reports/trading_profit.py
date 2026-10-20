"""Trading profit for week / month / year (net sales − COGS − expenses + income)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Count, ExpressionWrapper, F, Sum, fields as dj_fields
from django.utils import timezone
from expenses.models import Expense
from income.models import Income
from inventory.models import StockMovement
from reports.sale_scope import posted_sales
from sales.models import SaleItem, SaleRefund, SaleRefundItem

COGS_BREAKDOWN_SALE_LIMIT = 200

_LINE_COST = ExpressionWrapper(
    F('quantity') * F('unit_cost'),
    output_field=dj_fields.DecimalField(max_digits=14, decimal_places=2),
)
_REFUND_LINE_COST = ExpressionWrapper(
    F('quantity') * F('sale_item__unit_cost'),
    output_field=dj_fields.DecimalField(max_digits=14, decimal_places=2),
)


def _d(value) -> Decimal:
    return Decimal(str(value or 0))


def _money(value) -> float:
    return float(_d(value).quantize(Decimal('0.01')))


def _as_date(value):
    if value is None:
        return None
    if hasattr(value, 'date'):
        return value.date()
    return value


def _cogs_for_sales(sales_qs) -> Decimal:
    """FIFO-stamped line cost, with legacy sale-movement fallback (SQL only)."""
    sale_items = SaleItem.objects.filter(sale__in=sales_qs)
    with_cost = sale_items.filter(unit_cost__isnull=False).aggregate(total=Sum(_LINE_COST))['total']
    # Subquery — never materialise sale numbers into Python (scale-safe).
    legacy_refs = sale_items.filter(unit_cost__isnull=True).values_list(
        'sale__sale_number', flat=True
    )
    legacy = _d(
        StockMovement.objects.filter(
            movement_type='sale',
            reference__in=legacy_refs,
        ).aggregate(total=Sum('total_cost'))['total']
    )
    return _d(with_cost) + legacy


def _refund_cogs(refund_qs) -> Decimal:
    """Cost restored on refunds/voids — one SQL aggregate, not per-row Python."""
    total = (
        SaleRefundItem.objects.filter(
            refund__in=refund_qs,
            sale_item__unit_cost__isnull=False,
        ).aggregate(total=Sum(_REFUND_LINE_COST))['total']
    )
    return _d(total)


def _period_sales_and_refunds(*, start, end):
    sales_qs = posted_sales()
    if start is not None:
        sales_qs = sales_qs.filter(occurred_at__gte=start)
    if end is not None:
        sales_qs = sales_qs.filter(occurred_at__lte=end)

    refund_qs = SaleRefund.objects.filter(sale__status='completed')
    if start is not None:
        refund_qs = refund_qs.filter(created_at__gte=start)
    if end is not None:
        refund_qs = refund_qs.filter(created_at__lte=end)
    return sales_qs, refund_qs


def _trading_expenses_qs(*, start, end, included: bool = True):
    """
    Approved expenses filtered by category.include_in_trading_profit.

    Uncategorised expenses are treated as included (default contribute).
    """
    from django.db.models import Q

    # Aggregate-only path — no select_related (avoids useless JOINs at scale).
    expenses_qs = Expense.objects.filter(status='approved')
    if included:
        expenses_qs = expenses_qs.filter(
            Q(category__isnull=True) | Q(category__include_in_trading_profit=True)
        )
    else:
        expenses_qs = expenses_qs.filter(category__include_in_trading_profit=False)
    start_d = _as_date(start)
    end_d = _as_date(end)
    if start_d is not None:
        expenses_qs = expenses_qs.filter(expense_date__gte=start_d)
    if end_d is not None:
        expenses_qs = expenses_qs.filter(expense_date__lte=end_d)
    return expenses_qs


def compute_trading_profit(*, start, end) -> dict[str, Any]:
    """
    Net profit = (gross sales − refunds) − (COGS − refund COGS) − expenses + other income.

    Revenue uses Sale.total (tax-inclusive). ``tax_amount`` is returned for visibility only.
    Expenses: approved + category.include_in_trading_profit (default on per category).
    """
    sales_qs, refund_qs = _period_sales_and_refunds(start=start, end=end)

    sales_agg = sales_qs.aggregate(
        gross_sales=Sum('total'),
        tax_amount=Sum('tax_amount'),
        discount_amount=Sum('discount_amount'),
        sale_count=Count('id'),
    )
    sale_count = int(sales_agg['sale_count'] or 0)
    gross_sales = _d(sales_agg['gross_sales'])
    tax_amount = _d(sales_agg['tax_amount'])
    discount_amount = _d(sales_agg['discount_amount'])

    refund_agg = refund_qs.aggregate(total=Sum('amount'), refund_count=Count('id'))
    refunds_total = _d(refund_agg['total'])
    refund_count = int(refund_agg['refund_count'] or 0)

    net_sales = gross_sales - refunds_total
    cogs_sold = _cogs_for_sales(sales_qs)
    cogs_refunded = _refund_cogs(refund_qs)
    cogs = cogs_sold - cogs_refunded
    if cogs < 0:
        cogs = Decimal('0')

    expenses_qs = _trading_expenses_qs(start=start, end=end, included=True)
    exp_agg = expenses_qs.aggregate(total=Sum('amount'), expenses_count=Count('id'))
    expenses_total = _d(exp_agg['total'])
    expenses_count = int(exp_agg['expenses_count'] or 0)

    excluded_qs = _trading_expenses_qs(start=start, end=end, included=False)
    excl_agg = excluded_qs.aggregate(total=Sum('amount'), expenses_count=Count('id'))
    expenses_excluded_total = _d(excl_agg['total'])
    expenses_excluded_count = int(excl_agg['expenses_count'] or 0)

    start_d = _as_date(start)
    end_d = _as_date(end)
    income_qs = Income.objects.filter(status='approved')
    if start_d is not None:
        income_qs = income_qs.filter(income_date__gte=start_d)
    if end_d is not None:
        income_qs = income_qs.filter(income_date__lte=end_d)
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
        'expenses_count': expenses_count,
        'expenses_excluded': _money(expenses_excluded_total),
        'expenses_excluded_count': expenses_excluded_count,
        'other_income': _money(other_income),
        'purchases': _money(purchases_total),
        'net_profit': _money(net_profit),
        'profit_margin': round(margin, 2),
        'sale_count': sale_count,
        'refund_count': refund_count,
    }


def compute_cogs_breakdown(*, start, end, sale_limit: int = COGS_BREAKDOWN_SALE_LIMIT) -> dict[str, Any]:
    """
    How COGS was built for the period: per sale / line (unit_cost × qty),
    plus refund cost restored.
    """
    sales_qs, refund_qs = _period_sales_and_refunds(start=start, end=end)
    cogs_sold = _cogs_for_sales(sales_qs)
    cogs_refunded = _refund_cogs(refund_qs)
    cogs = cogs_sold - cogs_refunded
    if cogs < 0:
        cogs = Decimal('0')

    total_sales = sales_qs.count()
    sales_list = list(
        sales_qs.select_related('cashier')
        .order_by('-occurred_at', '-id')[:sale_limit]
    )
    sale_ids = [s.id for s in sales_list]
    items = (
        SaleItem.objects.filter(sale_id__in=sale_ids)
        .select_related('product', 'sale')
        .order_by('sale_id', 'id')
    )
    lines_by_sale: dict[int, list] = {sid: [] for sid in sale_ids}
    legacy_sale_numbers = set()
    for item in items:
        unit_cost = item.unit_cost
        qty = _d(item.quantity)
        if unit_cost is not None:
            line_cogs = _d(unit_cost) * qty
            source = 'unit_cost'
        else:
            line_cogs = Decimal('0')
            source = 'legacy_pending'
            if item.sale_id and item.sale.sale_number:
                legacy_sale_numbers.add(item.sale.sale_number)
        lines_by_sale[item.sale_id].append(
            {
                'product_name': getattr(item.product, 'name', None) or 'Item',
                'sku': getattr(item.product, 'sku', None) or '',
                'quantity': float(qty),
                'unit_cost': _money(unit_cost) if unit_cost is not None else None,
                'line_cogs': _money(line_cogs),
                'source': source,
            }
        )

    legacy_by_ref = {}
    if legacy_sale_numbers:
        for row in (
            StockMovement.objects.filter(
                movement_type='sale',
                reference__in=list(legacy_sale_numbers),
            )
            .values('reference')
            .annotate(total=Sum('total_cost'))
        ):
            legacy_by_ref[row['reference']] = _d(row['total'])

    sales_payload = []
    for sale in sales_list:
        lines = lines_by_sale.get(sale.id, [])
        sale_cogs = sum((_d(line['line_cogs']) for line in lines), Decimal('0'))
        if any(line['source'] == 'legacy_pending' for line in lines):
            legacy_total = legacy_by_ref.get(sale.sale_number, Decimal('0'))
            if legacy_total and sale_cogs == 0:
                sale_cogs = legacy_total
                lines.append(
                    {
                        'product_name': 'Legacy stock movements (no line unit cost)',
                        'sku': '',
                        'quantity': None,
                        'unit_cost': None,
                        'line_cogs': _money(legacy_total),
                        'source': 'legacy_movement',
                    }
                )
        sales_payload.append(
            {
                'sale_id': sale.id,
                'sale_number': sale.sale_number,
                'occurred_at': sale.occurred_at.isoformat() if sale.occurred_at else None,
                'sale_total': _money(sale.total),
                'cogs': _money(sale_cogs),
                'lines': lines,
            }
        )

    refund_rows = list(
        refund_qs.select_related('sale').order_by('-created_at', '-id')[:sale_limit]
    )
    refund_ids = [r.id for r in refund_rows]
    refund_items = (
        SaleRefundItem.objects.filter(refund_id__in=refund_ids)
        .select_related('product', 'sale_item', 'refund')
        .order_by('refund_id', 'id')
    )
    items_by_refund: dict[int, list] = {rid: [] for rid in refund_ids}
    for ri in refund_items:
        unit_cost = getattr(ri.sale_item, 'unit_cost', None) if ri.sale_item_id else None
        qty = _d(ri.quantity)
        line_cogs = (_d(unit_cost) * qty) if unit_cost is not None else Decimal('0')
        items_by_refund[ri.refund_id].append(
            {
                'product_name': getattr(ri.product, 'name', None) or 'Item',
                'quantity': float(qty),
                'unit_cost': _money(unit_cost) if unit_cost is not None else None,
                'line_cogs': _money(line_cogs),
            }
        )

    refunds_payload = []
    for refund in refund_rows:
        lines = items_by_refund.get(refund.id, [])
        restored = sum((_d(line['line_cogs']) for line in lines), Decimal('0'))
        refunds_payload.append(
            {
                'refund_id': refund.id,
                'sale_number': getattr(refund.sale, 'sale_number', '') or '',
                'created_at': refund.created_at.isoformat() if refund.created_at else None,
                'refund_amount': _money(refund.amount),
                'cogs_restored': _money(restored),
                'lines': lines,
            }
        )

    return {
        'date_from': start.isoformat() if start else None,
        'date_to': end.isoformat() if end else None,
        'cogs_sold': _money(cogs_sold),
        'cogs_refunded': _money(cogs_refunded),
        'cogs': _money(cogs),
        'sale_count': total_sales,
        'sales_shown': len(sales_payload),
        'truncated': total_sales > sale_limit,
        'explanation': (
            'COGS = sum of (quantity × unit cost) on sale lines in the period, '
            'minus cost restored on refunds/voids. Unit cost is stamped at sale (FIFO).'
        ),
        'sales': sales_payload,
        'refunds': refunds_payload,
    }


def _resolve_bounds(request):
    from reports.services import resolve_period

    params = getattr(request, 'query_params', request.GET)
    period = (params.get('period') or '').lower().strip()
    if not period and not params.get('date_from'):

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
    return start, end, period, label


def trading_profit_for_request(request) -> dict[str, Any]:
    start, end, period, label = _resolve_bounds(request)
    summary = compute_trading_profit(start=start, end=end)
    return {
        'period': period if period in ('week', 'month', 'year', 'today') else (label or 'custom'),
        'date_from': start.isoformat() if start else None,
        'date_to': end.isoformat() if end else None,
        'summary': summary,
    }


def trading_profit_cogs_for_request(request) -> dict[str, Any]:
    start, end, period, label = _resolve_bounds(request)
    breakdown = compute_cogs_breakdown(start=start, end=end)
    return {
        'period': period if period in ('week', 'month', 'year', 'today') else (label or 'custom'),
        **breakdown,
    }
