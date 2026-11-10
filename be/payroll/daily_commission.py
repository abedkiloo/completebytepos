"""Daily sales-agent commission from the editable band template."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Iterable

from django.db.models import F, Prefetch, Sum
from django.utils import timezone

from payroll.adapters.bonus import money, resolve_user_for_employee
from payroll.adapters.commission import _staff_sale_q, sales_commission_enabled
from payroll.commission_template import (
    DEFAULT_COMMISSION_TEMPLATE,
    commission_for_qualifying_sales,
    normalize_commission_template,
    product_name_excluded,
    transport_for_qualifying_sales,
)


def load_commission_template() -> dict[str, Any]:
    """
    Load the store commission template (PDF defaults when unset).

    Returns:
        Normalized template dict.
    """
    try:
        from payroll.models import PayrollSettings

        raw = getattr(PayrollSettings.load(), 'sales_commission_template', None)
    except Exception:
        raw = None
    return normalize_commission_template(raw or DEFAULT_COMMISSION_TEMPLATE)


def save_commission_template(raw) -> dict[str, Any]:
    """
    Persist a normalized commission template on PayrollSettings.

    Args:
        raw: Posted template mapping.

    Returns:
        Normalized template that was saved.

    Raises:
        ValueError: When payload is not a mapping.
    """
    if raw is not None and not isinstance(raw, dict):
        raise ValueError('Commission template must be an object.')
    from payroll.models import PayrollSettings

    normalized = normalize_commission_template(raw)
    settings = PayrollSettings.load()
    settings.sales_commission_template = normalized
    settings.save(update_fields=['sales_commission_template', 'updated_at'])
    return normalized


def _day_bounds(day: date):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), tz)
    end = timezone.make_aware(datetime.combine(day, time.max), tz)
    return start, end


def _period_bounds(start_day: date, end_day: date):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(start_day, time.min), tz)
    end = timezone.make_aware(datetime.combine(end_day, time.max), tz)
    return start, end


def _empty_day_info() -> dict[str, Any]:
    return {
        'qualifying_sales': Decimal('0.00'),
        'gross_attributed': Decimal('0.00'),
        'excluded_lines': Decimal('0.00'),
        'refunds': Decimal('0.00'),
        'sale_count': 0,
    }


def _refund_hit_on_qualifying(
    sale,
    sale_refund_total: Decimal,
    sale_q: Decimal,
    sale_x: Decimal,
    *,
    template: dict[str, Any],
) -> Decimal:
    """
    How much of a sale's refunds should reduce the commission base.

    Prefer ``SaleRefundItem`` rows when present (zip return stays on the zip
    line). Otherwise allocate the sale-level refund proportionally across
    qualifying vs non-qualifying lines so excluded products cannot fully
    drain kit commission.

    Args:
        sale: ``Sale`` with refunds/items available (prefetched when possible).
        sale_refund_total: Total refund amount for the sale in the window.
        sale_q: Qualifying line subtotal.
        sale_x: Non-qualifying line subtotal.
        template: Normalized commission template.

    Returns:
        Non-negative Decimal to subtract from ``sale_q`` (≤ ``sale_q``).
    """
    if sale_refund_total <= 0 or sale_q <= 0:
        return Decimal('0.00')

    line_refund_q = Decimal('0.00')
    line_refund_any = Decimal('0.00')
    try:
        refunds = sale.refunds.all()
    except Exception:
        refunds = []
    for refund in refunds:
        try:
            items = list(refund.items.all())
        except Exception:
            items = []
        if not items:
            continue
        for ritem in items:
            amt = money(ritem.subtotal)
            line_refund_any += amt
            prod = getattr(ritem, 'product', None)
            name = getattr(prod, 'name', '') if prod is not None else ''
            if not product_name_excluded(name, template):
                line_refund_q += amt

    if line_refund_any > 0:
        # Only the qualifying-line refund items reduce the award base.
        return money(min(sale_q, line_refund_q))

    sale_lines = sale_q + sale_x
    if sale_lines <= 0:
        return Decimal('0.00')
    share = (sale_q / sale_lines) * sale_refund_total
    return money(min(sale_q, share))


def _score_sales_for_template(
    sales: Iterable,
    refunds_by_sale_id: dict[int, Decimal],
    template: dict[str, Any],
) -> dict[str, Any]:
    """
    Score a batch of already-loaded sales into one qualifying-day total.

    Args:
        sales: Iterable of ``Sale`` with ``items`` (+ product) prefetched.
        refunds_by_sale_id: Sale id → refund amount in the same window.
        template: Normalized commission template.

    Returns:
        Dict with ``qualifying_sales``, ``gross_attributed``, ``excluded_lines``,
        ``refunds`` (refund portion allocated to qualifying lines), ``sale_count``.
    """
    tpl = template
    gross = Decimal('0.00')
    excluded = Decimal('0.00')
    refunds_on_qualifying = Decimal('0.00')
    sale_list = list(sales)
    for sale in sale_list:
        sale_q = Decimal('0.00')
        sale_x = Decimal('0.00')
        for item in sale.items.all():
            line = money(item.subtotal)
            name = getattr(item.product, 'name', '') if item.product_id else ''
            if product_name_excluded(name, tpl):
                sale_x += line
            else:
                sale_q += line
        sale_refund = money(refunds_by_sale_id.get(sale.pk, Decimal('0')))
        hit = _refund_hit_on_qualifying(
            sale, sale_refund, sale_q, sale_x, template=tpl
        )
        refunds_on_qualifying += hit
        gross += sale_q
        excluded += sale_x

    qualifying = money(max(Decimal('0.00'), gross - refunds_on_qualifying))
    return {
        'qualifying_sales': qualifying,
        'gross_attributed': money(gross),
        'excluded_lines': money(excluded),
        'refunds': money(refunds_on_qualifying),
        'sale_count': len(sale_list),
    }


def _load_agent_sales(
    user_id: int,
    start,
    end,
    *,
    template: dict[str, Any],
):
    """
    Load completed agent sales (+ items/products) for a datetime window.

    Args:
        user_id: Auth user id (> 0).
        start: Inclusive aware start.
        end: Inclusive aware end.
        template: Normalized template (field_only / full-pay flags).

    Returns:
        List of ``Sale`` instances with items and in-window refunds prefetched.
    """
    from reports.sale_scope import posted_sales
    from sales.models import SaleItem, SaleRefund

    qs = posted_sales().filter(_staff_sale_q(user_id)).filter(
        occurred_at__gte=start,
        occurred_at__lte=end,
    )
    if template.get('field_only', True):
        qs = qs.filter(entry_source='field')
    if template.get('require_full_payment_same_day', True):
        qs = qs.filter(amount_paid__gte=F('total'))
    return list(
        qs.prefetch_related(
            Prefetch(
                'items',
                queryset=SaleItem.objects.select_related('product'),
            ),
            Prefetch(
                'refunds',
                queryset=SaleRefund.objects.filter(
                    created_at__gte=start,
                    created_at__lte=end,
                ).prefetch_related('items__product'),
            ),
        )
    )


def _refunds_by_sale_id(sale_ids: list[int], start, end) -> dict[int, Decimal]:
    """
    Sum refunds per sale in a window (one query).

    Args:
        sale_ids: Sale primary keys (may be empty).
        start: Inclusive aware start.
        end: Inclusive aware end.

    Returns:
        Mapping sale_id → Decimal refund total (missing ids omitted).
    """
    from sales.models import SaleRefund

    if not sale_ids:
        return {}
    rows = (
        SaleRefund.objects.filter(
            sale_id__in=sale_ids,
            created_at__gte=start,
            created_at__lte=end,
        )
        .values('sale_id')
        .annotate(total=Sum('amount'))
    )
    return {int(row['sale_id']): money(row['total'] or 0) for row in rows}


def qualifying_sales_for_user_day(
    user_id: int,
    day: date,
    *,
    template: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Qualifying sales for one agent on one local calendar day.

    Rules (from the default template):
    - Field sales attributed to the agent (served_by else cashier).
    - Full payment same day (amount_paid ≥ total) when required.
    - Lines matching configurable keywords (e.g. zip) stay on sales views
      but do not count toward qualifying sales when the exclude option is on.
    - Same-day refunds allocated onto qualifying lines only.

    Args:
        user_id: Auth user id (> 0).
        day: Local business date.
        template: Optional normalized template.

    Returns:
        Dict with ``qualifying_sales``, ``gross_attributed``, ``excluded_lines``,
        ``refunds``, ``sale_count``.
    """
    tpl = normalize_commission_template(template or load_commission_template())
    start, end = _day_bounds(day)
    sales = _load_agent_sales(user_id, start, end, template=tpl)
    refunds = _refunds_by_sale_id([s.pk for s in sales], start, end)
    if not sales:
        return _empty_day_info()
    return _score_sales_for_template(sales, refunds, tpl)


def agent_day_commission(
    user_id: int,
    day: date | None = None,
    *,
    template: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build the agent dashboard payload for one day.

    Args:
        user_id: Auth user id.
        day: Local date (defaults to today).
        template: Optional template override.

    Returns:
        Dashboard dict: sales, commission band, transport, template bands.
    """
    tpl = normalize_commission_template(template or load_commission_template())
    target = day or timezone.localdate()
    sales_info = qualifying_sales_for_user_day(user_id, target, template=tpl)
    qualifying = sales_info['qualifying_sales']
    band = commission_for_qualifying_sales(qualifying, tpl)
    transport = transport_for_qualifying_sales(qualifying, tpl)
    return {
        'date': target.isoformat(),
        'is_today': target == timezone.localdate(),
        'enabled': sales_commission_enabled(),
        'scheme': tpl['scheme'],
        'qualifying_sales': str(qualifying),
        'gross_attributed': str(sales_info['gross_attributed']),
        'excluded_lines': str(sales_info['excluded_lines']),
        'refunds': str(sales_info['refunds']),
        'sale_count': sales_info['sale_count'],
        'commission': str(band['commission']),
        'band_min': band['band_min'],
        'band_max': band['band_max'],
        'band_index': band['band_index'],
        'next_band': band['next_band'],
        'transport': {
            'qualified': transport['qualified'],
            'amount': str(transport['amount']),
            'min_sales': str(transport['min_sales']),
            'note': (
                'Transport support for the following working day'
                if transport['qualified']
                else f"Need KES {transport['min_sales']} qualifying sales for transport"
            ),
        },
        'template': {
            'bands': tpl['bands'],
            'transport': tpl['transport'],
            'exclude_products_from_commission': tpl.get(
                'exclude_products_from_commission', True
            ),
            'exclude_product_keywords': tpl['exclude_product_keywords'],
            'field_only': tpl.get('field_only', True),
            'require_full_payment_same_day': tpl.get(
                'require_full_payment_same_day', True
            ),
        },
    }


def sum_daily_commissions_for_month(
    user_id: int,
    *,
    year: int,
    month: int,
    template: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Sum daily band commissions (+ transport) for a calendar month.

    Loads the month's field sales and refunds in a constant number of queries
    (not one query set per day), then scores each local day in memory.

    Args:
        user_id: Auth user id.
        year: Four-digit year.
        month: Month 1–12.
        template: Optional template.

    Returns:
        Dict with ``commission_total``, ``transport_total``, ``days`` list.
    """
    tpl = normalize_commission_template(template or load_commission_template())
    last = calendar.monthrange(year, month)[1]
    start_day = date(year, month, 1)
    end_day = date(year, month, last)
    start, end = _period_bounds(start_day, end_day)

    sales = _load_agent_sales(user_id, start, end, template=tpl)
    refunds = _refunds_by_sale_id([s.pk for s in sales], start, end)

    by_day: dict[date, list] = defaultdict(list)
    for sale in sales:
        local_day = timezone.localtime(sale.occurred_at).date()
        if start_day <= local_day <= end_day:
            by_day[local_day].append(sale)

    # Refunds keyed by sale; day scoring uses only that day's sales' refunds.
    commission_total = Decimal('0.00')
    transport_total = Decimal('0.00')
    days = []
    for day_n in range(1, last + 1):
        day = date(year, month, day_n)
        day_sales = by_day.get(day) or []
        if not day_sales:
            continue
        day_ids = {s.pk for s in day_sales}
        day_refunds = {
            sid: amt for sid, amt in refunds.items() if sid in day_ids
        }
        info = _score_sales_for_template(day_sales, day_refunds, tpl)
        if info['qualifying_sales'] <= 0 and info['sale_count'] == 0:
            continue
        band = commission_for_qualifying_sales(info['qualifying_sales'], tpl)
        transport = transport_for_qualifying_sales(info['qualifying_sales'], tpl)
        commission_total += band['commission']
        transport_total += transport['amount']
        days.append(
            {
                'date': day.isoformat(),
                'qualifying_sales': str(info['qualifying_sales']),
                'commission': str(band['commission']),
                'transport': str(transport['amount']),
            }
        )
    return {
        'commission_total': money(commission_total),
        'transport_total': money(transport_total),
        'amount': money(commission_total + transport_total),
        'days': days,
    }


def fetch_employee_daily_band_commission(
    employee,
    *,
    year: int,
    month: int,
) -> dict[str, Any]:
    """
    Payroll adapter entry: monthly total from daily bands for an employee.

    Args:
        employee: ``employees.Employee``.
        year: Payroll year.
        month: Payroll month 1–12.

    Returns:
        Same shape as ``fetch_sales_commission`` (amount, qualified, meta).
    """
    empty_meta = {
        'source': 'sales_commission',
        'scheme': 'daily_bands',
        'available': True,
        'period': f'{year}-{month:02d}',
    }
    empty = {'amount': Decimal('0.00'), 'qualified': False, 'meta': empty_meta}
    if not sales_commission_enabled():
        return {
            **empty,
            'meta': {**empty_meta, 'available': False, 'reason': 'commission_disabled'},
        }
    user = resolve_user_for_employee(employee)
    if user is None:
        return {
            **empty,
            'meta': {**empty_meta, 'matched_user': False, 'reason': 'no_user'},
        }
    tpl = load_commission_template()
    if tpl.get('scheme') != 'daily_bands':
        # Legacy percent path handled by caller.
        return {
            **empty,
            'meta': {**empty_meta, 'available': False, 'reason': 'not_daily_bands'},
        }
    summary = sum_daily_commissions_for_month(
        user.id, year=year, month=month, template=tpl
    )
    amount = summary['amount']
    return {
        'amount': amount,
        'qualified': amount > 0,
        'meta': {
            **empty_meta,
            'matched_user': True,
            'user_id': user.id,
            'commission_total': str(summary['commission_total']),
            'transport_total': str(summary['transport_total']),
            'days': summary['days'],
            'template_scheme': 'daily_bands',
        },
    }
