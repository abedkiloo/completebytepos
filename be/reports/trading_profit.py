"""Trading profit for week / month / year (net sales − COGS − expenses + income)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Count, ExpressionWrapper, F, Q, Sum, Value, fields as dj_fields
from django.db.models.functions import Coalesce, Greatest, Least
from django.utils import timezone
from expenses.models import Expense
from income.models import Income
from inventory.models import StockMovement
from reports.sale_scope import posted_sales
from sales.models import (
    CustomerWalletTransaction,
    SaleItem,
    SaleItemLayerAllocation,
    SaleRefund,
    SaleRefundItem,
)

COGS_BREAKDOWN_SALE_LIMIT = 200

_DEC = dj_fields.DecimalField(max_digits=14, decimal_places=2)
_LINE_COST = ExpressionWrapper(
    F('quantity') * F('unit_cost'),
    output_field=_DEC,
)
# Net of admin-return / refund restores so superseded slices cannot inflate COGS.
_ALLOC_COST = ExpressionWrapper(
    Greatest(F('quantity') - Coalesce(F('qty_returned'), Value(0)), Value(0))
    * F('unit_cost'),
    output_field=_DEC,
)
_REFUND_LINE_COST = ExpressionWrapper(
    F('quantity') * F('sale_item__unit_cost'),
    output_field=_DEC,
)
_ZERO = Value(Decimal('0'), output_field=_DEC)
_CATALOG_LINE_COST = ExpressionWrapper(
    F('quantity') * Coalesce(F('variant__cost'), F('product__cost'), _ZERO),
    output_field=_DEC,
)


def _d(value) -> Decimal:
    return Decimal(str(value or 0))


def _money(value) -> float:
    return float(_d(value).quantize(Decimal('0.01')))


def _as_date(value):
    """Calendar day in the active Django timezone (not raw UTC ``.date()``)."""
    if value is None:
        return None
    if hasattr(value, 'date') and callable(value.date):
        if timezone.is_aware(value):
            return timezone.localtime(value).date()
        return value.date()
    return value


def _unit_cost_missing(unit_cost) -> bool:
    """Stamped 0 is treated as missing — catalog default 0 must not hide real COGS."""
    if unit_cost is None:
        return True
    return _d(unit_cost) <= 0


def _cogs_for_sales(sales_qs) -> Decimal:
    """
    Line COGS with fallbacks when ``SaleItem.unit_cost`` is null or 0.

    Order: positive stamped cost → FIFO layer allocations → sale stock movements
    (gap vs already-counted lines) → current catalog cost on remaining zero lines.
    """
    sale_items = SaleItem.objects.filter(sale__in=sales_qs)
    positive = _d(
        sale_items.filter(unit_cost__gt=0).aggregate(total=Sum(_LINE_COST))['total']
    )

    unresolved = sale_items.filter(Q(unit_cost__isnull=True) | Q(unit_cost__lte=0))
    if not unresolved.exists():
        return positive

    # FIFO slices stamped at sale even when the line unit_cost was left 0/null.
    from_alloc = _d(
        SaleItemLayerAllocation.objects.filter(
            sale_item__in=unresolved,
            unit_cost__gt=0,
        ).aggregate(total=Sum(_ALLOC_COST))['total']
    )
    covered_by_alloc = set(
        SaleItemLayerAllocation.objects.filter(
            sale_item__in=unresolved,
            unit_cost__gt=0,
        ).values_list('sale_item_id', flat=True)
    )
    still_open = unresolved.exclude(id__in=covered_by_alloc) if covered_by_alloc else unresolved

    movement_gap = Decimal('0')
    catalog = Decimal('0')
    if still_open.exists():
        # Movements for the same sale + product as unresolved lines (not whole-sale totals).
        open_keys = {
            (ref, product_id)
            for ref, product_id in still_open.values_list('sale__sale_number', 'product_id')
            if ref
        }
        refs = {ref for ref, _pid in open_keys}
        mov_by_ref_product = {
            (row['reference'], row['product_id']): _d(row['total'])
            for row in (
                StockMovement.objects.filter(movement_type='sale', reference__in=refs)
                .values('reference', 'product_id')
                .annotate(total=Sum('total_cost'))
            )
        }
        covered_product_keys = set()
        for ref, product_id in open_keys:
            mov = mov_by_ref_product.get((ref, product_id), Decimal('0'))
            if mov > 0:
                movement_gap += mov
                covered_product_keys.add((ref, product_id))

        # Catalog only for unresolved lines whose sale+product had no movement cost.
        if covered_product_keys:
            q = Q()
            for ref, product_id in covered_product_keys:
                q |= Q(sale__sale_number=ref, product_id=product_id)
            catalog_qs = still_open.exclude(q)
        else:
            catalog_qs = still_open
        catalog = _d(catalog_qs.aggregate(total=Sum(_CATALOG_LINE_COST))['total'])

    return positive + from_alloc + movement_gap + catalog


def _refund_cogs(refund_qs) -> Decimal:
    """Cost restored on refunds — positive stamped cost, else catalog on the sale line."""
    items = SaleRefundItem.objects.filter(refund__in=refund_qs)
    stamped = _d(
        items.filter(sale_item__unit_cost__gt=0).aggregate(total=Sum(_REFUND_LINE_COST))['total']
    )
    # Null/zero sale_item cost: restore using catalog so voids match sold COGS fallbacks.
    missing = items.filter(
        Q(sale_item__unit_cost__isnull=True) | Q(sale_item__unit_cost__lte=0)
    )
    catalog = _d(
        missing.annotate(
            eff=Coalesce(
                F('sale_item__variant__cost'),
                F('sale_item__product__cost'),
                _ZERO,
            ),
        )
        .filter(eff__gt=0)
        .aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('quantity') * F('eff'),
                    output_field=_DEC,
                )
            )
        )['total']
    )
    return stamped + catalog


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

    collected_expr = ExpressionWrapper(
        Least(F('amount_paid'), F('total')),
        output_field=_DEC,
    )
    unpaid_expr = ExpressionWrapper(
        Greatest(F('total') - F('amount_paid'), _ZERO),
        output_field=_DEC,
    )
    sales_agg = sales_qs.aggregate(
        gross_sales=Sum('total'),
        tax_amount=Sum('tax_amount'),
        discount_amount=Sum('discount_amount'),
        sale_count=Count('id'),
        # Cash taken on these sales (never above the sale total).
        collected_on_sales=Sum(collected_expr),
        # Still owed on these sales (wallet debt + invoice outstanding).
        unpaid_on_sales=Sum(unpaid_expr),
    )
    sale_count = int(sales_agg['sale_count'] or 0)
    gross_sales = _d(sales_agg['gross_sales'])
    tax_amount = _d(sales_agg['tax_amount'])
    discount_amount = _d(sales_agg['discount_amount'])
    collected_on_sales = _d(sales_agg['collected_on_sales'])
    unpaid_on_sales = _d(sales_agg['unpaid_on_sales'])

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

    # Debt settlements received in the period (cash in — may clear older sales).
    settlements_qs = CustomerWalletTransaction.objects.filter(
        source_type='debt_settlement',
        transaction_type='credit',
    )
    if start is not None:
        settlements_qs = settlements_qs.filter(created_at__gte=start)
    if end is not None:
        settlements_qs = settlements_qs.filter(created_at__lte=end)
    debt_collections = _d(settlements_qs.aggregate(total=Sum('amount'))['total'])

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

    # Cash trading profit: same COGS/expenses/income, but revenue = cash taken
    # on period sales + debt settlements received in the period (not unpaid).
    cash_in_period = collected_on_sales + debt_collections
    cash_gross_profit = cash_in_period - cogs
    cash_net_profit = cash_gross_profit - expenses_total + other_income
    cash_margin = (
        float(cash_net_profit / cash_in_period * 100) if cash_in_period > 0 else 0.0
    )

    return {
        'basis': 'trading',
        'formula': 'net_sales - cogs - expenses + other_income',
        'cash_formula': (
            '(collected_on_sales + debt_collections) - cogs - expenses + other_income'
        ),
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
        # Cash vs debt + cash trading profit (same period costs).
        'collected_on_sales': _money(collected_on_sales),
        'unpaid_on_sales': _money(unpaid_on_sales),
        'debt_collections': _money(debt_collections),
        'cash_in_period': _money(cash_in_period),
        'cash_gross_profit': _money(cash_gross_profit),
        'cash_net_profit': _money(cash_net_profit),
        'cash_profit_margin': round(cash_margin, 2),
        'cash_vs_debt_note': (
            'Trading profit (accrual) uses full sale totals including unpaid / debt. '
            'Cash trading profit uses only money collected on these sales plus debt '
            'collections received this period, with the same COGS and expenses. '
            'When customers still owe, cash profit is lower than trading profit.'
        ),
    }


def compute_cogs_breakdown(*, start, end, sale_limit: int = COGS_BREAKDOWN_SALE_LIMIT) -> dict[str, Any]:
    """
    How COGS was built for the period: per sale / line, with the same fallbacks
    as ``_cogs_for_sales`` (stamped → layers → movements → catalog).
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
    items = list(
        SaleItem.objects.filter(sale_id__in=sale_ids)
        .select_related('product', 'variant', 'sale')
        .order_by('sale_id', 'id')
    )
    items_by_sale: dict[int, list] = {sid: [] for sid in sale_ids}
    for item in items:
        items_by_sale[item.sale_id].append(item)

    sale_numbers = [s.sale_number for s in sales_list if s.sale_number]
    mov_rows = (
        StockMovement.objects.filter(movement_type='sale', reference__in=sale_numbers)
        .values('reference', 'product_id')
        .annotate(total=Sum('total_cost'))
    )
    mov_by_sale_product: dict[str, dict[int, Decimal]] = {}
    for row in mov_rows:
        ref = row['reference']
        mov_by_sale_product.setdefault(ref, {})[row['product_id']] = _d(row['total'])

    alloc_by_item: dict[int, Decimal] = {
        row['sale_item_id']: _d(row['total'])
        for row in (
            SaleItemLayerAllocation.objects.filter(
                sale_item_id__in=[i.id for i in items],
                unit_cost__gt=0,
            )
            .values('sale_item_id')
            .annotate(total=Sum(_ALLOC_COST))
        )
    }

    sales_payload = []
    for sale in sales_list:
        sale_items = items_by_sale.get(sale.id, [])
        mov_for_sale = dict(mov_by_sale_product.get(sale.sale_number, {}))

        # Unresolved qty per product (for splitting movement totals across duplicate lines).
        unresolved_qty: dict[int, Decimal] = {}
        for item in sale_items:
            if _unit_cost_missing(item.unit_cost) and item.id not in alloc_by_item:
                unresolved_qty[item.product_id] = unresolved_qty.get(item.product_id, Decimal('0')) + _d(item.quantity)

        lines = []
        sale_cogs = Decimal('0')
        for item in sale_items:
            qty = _d(item.quantity)
            product_name = getattr(item.product, 'name', None) or 'Item'
            sku = getattr(item.product, 'sku', None) or ''

            if not _unit_cost_missing(item.unit_cost):
                uc = _d(item.unit_cost)
                line_cogs = uc * qty
                source = 'unit_cost'
                display_uc = uc
            elif item.id in alloc_by_item:
                line_cogs = alloc_by_item[item.id]
                display_uc = (line_cogs / qty) if qty else line_cogs
                source = 'layer_allocation'
            else:
                mov_total = mov_for_sale.get(item.product_id, Decimal('0'))
                uqty = unresolved_qty.get(item.product_id, Decimal('0'))
                if mov_total > 0 and uqty > 0 and qty > 0:
                    line_cogs = (mov_total * qty / uqty).quantize(Decimal('0.01'))
                    display_uc = (line_cogs / qty) if qty else line_cogs
                    source = 'stock_movement'
                else:
                    catalog = None
                    if item.variant_id and item.variant is not None:
                        catalog = item.variant.cost
                    elif item.product is not None:
                        catalog = item.product.cost
                    if catalog is not None and _d(catalog) > 0:
                        display_uc = _d(catalog)
                        line_cogs = display_uc * qty
                        source = 'catalog'
                    elif item.unit_cost is not None:
                        display_uc = Decimal('0')
                        line_cogs = Decimal('0')
                        source = 'unit_cost'
                    else:
                        display_uc = None
                        line_cogs = Decimal('0')
                        source = 'legacy_pending'

            sale_cogs += line_cogs
            cost_missing = line_cogs <= 0 and source in (
                'unit_cost', 'legacy_pending', 'catalog',
            )
            lines.append(
                {
                    'product_name': product_name,
                    'sku': sku,
                    'quantity': float(qty),
                    'unit_cost': _money(display_uc) if display_uc is not None else None,
                    'line_cogs': _money(line_cogs),
                    'source': source,
                    'cost_missing': cost_missing,
                }
            )

        # Pure-null legacy sales with no per-line resolution: show movement total once.
        if (
            lines
            and all(line['source'] == 'legacy_pending' for line in lines)
            and sale.sale_number
        ):
            legacy_total = sum(mov_for_sale.values(), Decimal('0'))
            if legacy_total > 0:
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

        missing_names = [
            line['product_name'] for line in lines
            if line.get('cost_missing') and line.get('product_name')
            and line['product_name'] != 'Legacy stock movements (no line unit cost)'
        ]
        concerns = []
        if missing_names:
            concerns.append(
                'No cost on: '
                + ', '.join(dict.fromkeys(missing_names))
                + '. Set cost on the product/sizes — all goods must have a cost.'
            )
        if any(line.get('source') == 'legacy_movement' for line in lines):
            concerns.append(
                'COGS came from stock movements because sale lines had no unit cost. '
                'Newer sales stamp cost at checkout; fix product costs so this stops recurring.'
            )
        elif any(line.get('source') == 'stock_movement' for line in lines):
            concerns.append(
                'Some lines used stock-movement cost because the stamped line cost was 0. '
                'Prefer fixing product/size costs so checkout stamps the right cost.'
            )

        sales_payload.append(
            {
                'sale_id': sale.id,
                'sale_number': sale.sale_number,
                'occurred_at': sale.occurred_at.isoformat() if sale.occurred_at else None,
                'sale_total': _money(sale.total),
                'cogs': _money(sale_cogs),
                'lines': lines,
                'concerns': concerns,
            }
        )

    refund_rows = list(
        refund_qs.select_related('sale').order_by('-created_at', '-id')[:sale_limit]
    )
    refund_ids = [r.id for r in refund_rows]
    refund_items = (
        SaleRefundItem.objects.filter(refund_id__in=refund_ids)
        .select_related('product', 'sale_item', 'sale_item__product', 'sale_item__variant', 'refund')
        .order_by('refund_id', 'id')
    )
    items_by_refund: dict[int, list] = {rid: [] for rid in refund_ids}
    for ri in refund_items:
        qty = _d(ri.quantity)
        unit_cost = getattr(ri.sale_item, 'unit_cost', None) if ri.sale_item_id else None
        if unit_cost is not None and _d(unit_cost) > 0:
            line_cogs = _d(unit_cost) * qty
            display_uc = _d(unit_cost)
        else:
            catalog = None
            if ri.sale_item_id:
                if ri.sale_item.variant_id and ri.sale_item.variant is not None:
                    catalog = ri.sale_item.variant.cost
                elif ri.sale_item.product is not None:
                    catalog = ri.sale_item.product.cost
            if catalog is not None and _d(catalog) > 0:
                display_uc = _d(catalog)
                line_cogs = display_uc * qty
            else:
                display_uc = _d(unit_cost) if unit_cost is not None else None
                line_cogs = Decimal('0')
        items_by_refund[ri.refund_id].append(
            {
                'product_name': getattr(ri.product, 'name', None) or 'Item',
                'quantity': float(qty),
                'unit_cost': _money(display_uc) if display_uc is not None else None,
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
            'COGS = quantity × unit cost on each sale line (FIFO stamp). '
            'When a line is missing or 0, cost is taken from FIFO layer slices, '
            'then that sale’s stock movements, then the product catalog cost. '
            'Lines still at 0 are flagged — every tracked product must have a cost.'
        ),
        'sales': sales_payload,
        'refunds': refunds_payload,
        'cost_missing_sale_count': sum(1 for s in sales_payload if s.get('concerns')),
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


BREAKDOWN_ROW_LIMIT = 200

# Metrics the UI can drill into from trading-profit rows.
BREAKDOWN_METRICS = frozenset({
    'gross_sales',
    'refunds',
    'net_sales',
    'cogs',
    'gross_profit',
    'expenses',
    'expenses_excluded',
    'other_income',
    'net_profit',
    'collected_on_sales',
    'debt_collections',
    'cash_in_period',
    'unpaid_on_sales',
    'cash_gross_profit',
    'cash_net_profit',
})


def _iso_dt(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def _sale_row(sale, *, amount_key: str = 'total') -> dict[str, Any]:
    unpaid = max(_d(sale.total) - _d(sale.amount_paid), Decimal('0'))
    collected = min(_d(sale.amount_paid), _d(sale.total))
    amount = {
        'total': _d(sale.total),
        'collected': collected,
        'unpaid': unpaid,
    }.get(amount_key, _d(sale.total))
    lines = []
    for item in sale.items.all():
        line_total = (
            item.subtotal
            if item.subtotal is not None
            else _d(item.quantity) * _d(item.unit_price)
        )
        lines.append({
            'product_name': getattr(item.product, 'name', None) or 'Item',
            'quantity': float(_d(item.quantity)),
            'unit_price': _money(item.unit_price),
            'line_total': _money(line_total),
        })
    occurred = _as_date(sale.occurred_at) or ''
    return {
        'id': sale.id,
        'label': sale.sale_number or f'Sale #{sale.id}',
        'sublabel': f'{occurred} · {sale.payment_method or "—"} · paid {_money(sale.amount_paid)}',
        'amount': _money(amount),
        'sale_total': _money(sale.total),
        'amount_paid': _money(sale.amount_paid),
        'unpaid': _money(unpaid),
        'occurred_at': _iso_dt(sale.occurred_at),
        'lines': lines,
    }


def _component(label: str, value, *, op: str = '') -> dict[str, Any]:
    return {'label': label, 'value': _money(value), 'op': op}


def compute_metric_breakdown(
    *,
    metric: str,
    start,
    end,
    row_limit: int = BREAKDOWN_ROW_LIMIT,
) -> dict[str, Any]:
    """
    Drill-down for one trading-profit line: formula steps + contributing rows.

    ``metric=cogs`` reuses the detailed COGS sale/line builder.
    """
    metric = (metric or '').strip().lower()
    if metric not in BREAKDOWN_METRICS:
        raise ValueError(
            f'Unknown metric "{metric}". Choose one of: '
            + ', '.join(sorted(BREAKDOWN_METRICS))
        )

    summary = compute_trading_profit(start=start, end=end)
    sales_qs, refund_qs = _period_sales_and_refunds(start=start, end=end)
    base = {
        'metric': metric,
        'date_from': start.isoformat() if start else None,
        'date_to': end.isoformat() if end else None,
        'total': summary.get(metric if metric != 'net_profit' else 'net_profit'),
        'components': [],
        'rows': [],
        'row_count': 0,
        'rows_shown': 0,
        'truncated': False,
        'cogs': None,
    }

    if metric == 'cogs':
        cogs = compute_cogs_breakdown(start=start, end=end, sale_limit=row_limit)
        return {
            **base,
            'title': 'COGS (cost of goods sold)',
            'explanation': cogs.get('explanation') or '',
            'formula': 'COGS sold − cost restored on refunds',
            'total': cogs.get('cogs'),
            'components': [
                _component('COGS sold', cogs.get('cogs_sold') or 0),
                _component('Refunded cost', cogs.get('cogs_refunded') or 0, op='−'),
                _component('Net COGS', cogs.get('cogs') or 0, op='='),
            ],
            'cogs': cogs,
            'row_count': cogs.get('sale_count') or 0,
            'rows_shown': cogs.get('sales_shown') or 0,
            'truncated': bool(cogs.get('truncated')),
        }

    if metric == 'gross_sales':
        total_count = sales_qs.count()
        sales = list(
            sales_qs.select_related('customer')
            .prefetch_related('items__product')
            .order_by('-occurred_at', '-id')[:row_limit]
        )
        rows = [_sale_row(s, amount_key='total') for s in sales]
        return {
            **base,
            'title': 'Gross sales',
            'explanation': (
                'Sum of completed sale totals in this period (business date). '
                'Each sale below shows its line items.'
            ),
            'formula': 'Sum of sale totals',
            'total': summary['gross_sales'],
            'rows': rows,
            'row_count': total_count,
            'rows_shown': len(rows),
            'truncated': total_count > row_limit,
        }

    if metric == 'refunds':
        total_count = refund_qs.count()
        refunds = list(
            refund_qs.select_related('sale')
            .order_by('-created_at', '-id')[:row_limit]
        )
        rows = []
        for refund in refunds:
            sale = refund.sale
            rows.append({
                'id': refund.id,
                'label': getattr(refund, 'refund_number', None) or f'Refund #{refund.id}',
                'sublabel': (
                    f'On {sale.sale_number if sale else "sale"} · '
                    f'{_as_date(refund.created_at) or ""}'
                ),
                'amount': _money(refund.amount),
                'lines': [],
            })
        return {
            **base,
            'title': 'Refunds / voids',
            'explanation': (
                'Approved refunds and voids applied in this period. '
                'They reduce gross sales to net sales.'
            ),
            'formula': 'Sum of refund amounts',
            'total': summary['refunds'],
            'rows': rows,
            'row_count': total_count,
            'rows_shown': len(rows),
            'truncated': total_count > row_limit,
        }

    if metric == 'net_sales':
        return {
            **base,
            'title': 'Net sales',
            'explanation': 'Gross sales after refunds and voids in the period.',
            'formula': 'Gross sales − refunds / voids',
            'total': summary['net_sales'],
            'components': [
                _component('Gross sales', summary['gross_sales']),
                _component('Refunds / voids', summary['refunds'], op='−'),
                _component('Net sales', summary['net_sales'], op='='),
            ],
            'rows': [],
            'row_count': 0,
            'rows_shown': 0,
            'truncated': False,
        }

    if metric == 'gross_profit':
        return {
            **base,
            'title': 'Gross profit',
            'explanation': (
                'Net sales minus the cost of goods sold for those sales. '
                'Open Net sales or COGS for the underlying documents.'
            ),
            'formula': 'Net sales − COGS',
            'total': summary['gross_profit'],
            'components': [
                _component('Net sales', summary['net_sales']),
                _component('COGS', summary['cogs'], op='−'),
                _component('Gross profit', summary['gross_profit'], op='='),
            ],
        }

    if metric in ('expenses', 'expenses_excluded'):
        included = metric == 'expenses'
        expenses_qs = _trading_expenses_qs(start=start, end=end, included=included)
        total_count = expenses_qs.count()
        expenses = list(
            expenses_qs.select_related('category')
            .order_by('-expense_date', '-id')[:row_limit]
        )
        rows = [
            {
                'id': exp.id,
                'label': exp.expense_number or f'Expense #{exp.id}',
                'sublabel': (
                    f'{exp.expense_date} · '
                    f'{getattr(exp.category, "name", None) or "Uncategorised"} · '
                    f'{(exp.description or "")[:80]}'
                ),
                'amount': _money(exp.amount),
                'lines': [],
            }
            for exp in expenses
        ]
        return {
            **base,
            'title': 'Expenses (in trading profit)' if included else 'Excluded expenses',
            'explanation': (
                'Approved expenses whose category is included in trading profit.'
                if included
                else 'Approved expenses on categories marked excluded from trading profit '
                     '(e.g. owner drawings). Shown for visibility only.'
            ),
            'formula': 'Sum of approved expense amounts',
            'total': summary['expenses'] if included else summary['expenses_excluded'],
            'rows': rows,
            'row_count': total_count,
            'rows_shown': len(rows),
            'truncated': total_count > row_limit,
        }

    if metric == 'other_income':
        start_d = _as_date(start)
        end_d = _as_date(end)
        income_qs = Income.objects.filter(status='approved')
        if start_d is not None:
            income_qs = income_qs.filter(income_date__gte=start_d)
        if end_d is not None:
            income_qs = income_qs.filter(income_date__lte=end_d)
        total_count = income_qs.count()
        incomes = list(
            income_qs.select_related('category')
            .order_by('-income_date', '-id')[:row_limit]
        )
        rows = [
            {
                'id': inc.id,
                'label': getattr(inc, 'income_number', None) or f'Income #{inc.id}',
                'sublabel': (
                    f'{inc.income_date} · '
                    f'{getattr(inc.category, "name", None) or "Uncategorised"} · '
                    f'{(inc.description or "")[:80]}'
                ),
                'amount': _money(inc.amount),
                'lines': [],
            }
            for inc in incomes
        ]
        return {
            **base,
            'title': 'Other income',
            'explanation': 'Approved other income in the period (added to trading profit).',
            'formula': 'Sum of approved other income',
            'total': summary['other_income'],
            'rows': rows,
            'row_count': total_count,
            'rows_shown': len(rows),
            'truncated': total_count > row_limit,
        }

    if metric == 'net_profit':
        return {
            **base,
            'title': 'Trading profit',
            'explanation': (
                'Accrual trading profit: full net sales (including unpaid), '
                'minus COGS and included expenses, plus other income.'
            ),
            'formula': 'Net sales − COGS − expenses + other income',
            'total': summary['net_profit'],
            'components': [
                _component('Net sales', summary['net_sales']),
                _component('COGS', summary['cogs'], op='−'),
                _component('Expenses', summary['expenses'], op='−'),
                _component('Other income', summary['other_income'], op='+'),
                _component('Trading profit', summary['net_profit'], op='='),
            ],
        }

    if metric == 'collected_on_sales':
        total_count = sales_qs.count()
        sales = list(
            sales_qs.select_related('customer')
            .prefetch_related('items__product')
            .order_by('-occurred_at', '-id')[:row_limit]
        )
        rows = [_sale_row(s, amount_key='collected') for s in sales]
        return {
            **base,
            'title': 'Collected on these sales',
            'explanation': (
                'Cash/M-PESA/etc. taken on sales in this period, capped at each sale total. '
                'Does not include later debt collections.'
            ),
            'formula': 'Sum of min(amount paid, sale total) on period sales',
            'total': summary['collected_on_sales'],
            'rows': rows,
            'row_count': total_count,
            'rows_shown': len(rows),
            'truncated': total_count > row_limit,
        }

    if metric == 'unpaid_on_sales':
        unpaid_qs = sales_qs.annotate(
            _unpaid=ExpressionWrapper(
                Greatest(F('total') - F('amount_paid'), _ZERO),
                output_field=_DEC,
            )
        ).filter(_unpaid__gt=0)
        total_count = unpaid_qs.count()
        sales = list(
            unpaid_qs.select_related('customer')
            .prefetch_related('items__product')
            .order_by('-occurred_at', '-id')[:row_limit]
        )
        rows = [_sale_row(s, amount_key='unpaid') for s in sales]
        return {
            **base,
            'title': 'Still unpaid on these sales',
            'explanation': (
                'Amount still owed on period sales (sale total − amount paid). '
                'Counted in accrual trading profit, not in cash trading profit.'
            ),
            'formula': 'Sum of max(sale total − amount paid, 0)',
            'total': summary['unpaid_on_sales'],
            'rows': rows,
            'row_count': total_count,
            'rows_shown': len(rows),
            'truncated': total_count > row_limit,
        }

    if metric == 'debt_collections':
        settlements_qs = CustomerWalletTransaction.objects.filter(
            source_type='debt_settlement',
            transaction_type='credit',
        )
        if start is not None:
            settlements_qs = settlements_qs.filter(created_at__gte=start)
        if end is not None:
            settlements_qs = settlements_qs.filter(created_at__lte=end)
        total_count = settlements_qs.count()
        txns = list(
            settlements_qs.select_related('customer', 'sale')
            .order_by('-created_at', '-id')[:row_limit]
        )
        rows = []
        for txn in txns:
            customer_name = getattr(txn.customer, 'name', None) or 'Customer'
            sale_ref = txn.sale.sale_number if txn.sale_id and txn.sale else ''
            rows.append({
                'id': txn.id,
                'label': customer_name,
                'sublabel': (
                    f'{_as_date(txn.created_at) or ""}'
                    + (f' · {sale_ref}' if sale_ref else '')
                    + (f' · {(txn.notes or "")[:60]}' if txn.notes else '')
                ),
                'amount': _money(txn.amount),
                'lines': [],
            })
        return {
            **base,
            'title': 'Debt collections this period',
            'explanation': (
                'Payments received against customer debt in this period '
                '(may clear older sales).'
            ),
            'formula': 'Sum of debt settlement credits',
            'total': summary['debt_collections'],
            'rows': rows,
            'row_count': total_count,
            'rows_shown': len(rows),
            'truncated': total_count > row_limit,
        }

    if metric == 'cash_in_period':
        return {
            **base,
            'title': 'Cash in',
            'explanation': (
                'Money collected on period sales plus debt collections received '
                'in the period.'
            ),
            'formula': 'Collected on these sales + debt collections',
            'total': summary['cash_in_period'],
            'components': [
                _component('Collected on these sales', summary['collected_on_sales']),
                _component('Debt collections', summary['debt_collections'], op='+'),
                _component('Cash in', summary['cash_in_period'], op='='),
            ],
        }

    if metric == 'cash_gross_profit':
        return {
            **base,
            'title': 'Cash gross profit',
            'explanation': 'Cash in for the period minus the same COGS as accrual trading profit.',
            'formula': 'Cash in − COGS',
            'total': summary['cash_gross_profit'],
            'components': [
                _component('Cash in', summary['cash_in_period']),
                _component('COGS', summary['cogs'], op='−'),
                _component('Cash gross profit', summary['cash_gross_profit'], op='='),
            ],
        }

    # cash_net_profit
    return {
        **base,
        'title': 'Cash trading profit',
        'explanation': (
            'Cash in minus COGS and expenses, plus other income. '
            'Uses the same costs as accrual trading profit.'
        ),
        'formula': 'Cash in − COGS − expenses + other income',
        'total': summary['cash_net_profit'],
        'components': [
            _component('Cash in', summary['cash_in_period']),
            _component('COGS', summary['cogs'], op='−'),
            _component('Expenses', summary['expenses'], op='−'),
            _component('Other income', summary['other_income'], op='+'),
            _component('Cash trading profit', summary['cash_net_profit'], op='='),
        ],
    }


def trading_profit_breakdown_for_request(request) -> dict[str, Any]:
    from django.core.exceptions import ValidationError

    start, end, period, label = _resolve_bounds(request)
    params = getattr(request, 'query_params', request.GET)
    metric = (params.get('metric') or '').strip().lower()
    if not metric:
        raise ValidationError({'metric': 'Query param metric is required.'})
    try:
        breakdown = compute_metric_breakdown(metric=metric, start=start, end=end)
    except ValueError as exc:
        raise ValidationError({'metric': str(exc)}) from exc
    return {
        'period': period if period in ('week', 'month', 'year', 'today') else (label or 'custom'),
        **breakdown,
    }
