"""Trading profit for week / month / year (net sales − COGS − expenses + income)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Count, ExpressionWrapper, F, Q, Sum, Value, fields as dj_fields
from django.db.models.functions import Coalesce
from django.utils import timezone
from expenses.models import Expense
from income.models import Income
from inventory.models import StockMovement
from reports.sale_scope import posted_sales
from sales.models import SaleItem, SaleItemLayerAllocation, SaleRefund, SaleRefundItem

COGS_BREAKDOWN_SALE_LIMIT = 200

_DEC = dj_fields.DecimalField(max_digits=14, decimal_places=2)
_LINE_COST = ExpressionWrapper(
    F('quantity') * F('unit_cost'),
    output_field=_DEC,
)
_ALLOC_COST = ExpressionWrapper(
    F('quantity') * F('unit_cost'),
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
