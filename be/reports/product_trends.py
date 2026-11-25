"""
Per-product monthly sales and receiving trends for the product detail desk.

Used when a staff member opens a product and wants month-over-month
performance (units sold, revenue, orders) plus how stock was received.
"""

from __future__ import annotations

from calendar import month_abbr
from datetime import date, datetime, time
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from reports.sale_scope import posted_sale_items
from settings.module_features import is_module_feature_enabled
from settings.settings_service import SettingsService

MODULE = 'reports'
MAX_MONTHS = 24
DEFAULT_MONTHS = 12


def product_trends_feature_enabled() -> bool:
    """
    Whether the product trends package feature is on.

    Returns:
        bool: True when ``reports.product_trends`` is enabled. Uses the
        registry default (on) when the feature row is missing. No writes.
    """
    return is_module_feature_enabled(MODULE, 'product_trends')


def product_trends_allowed() -> bool:
    """
    Store may use product trends (setting + package feature).

    Returns:
        bool: True when product reports ModuleSetting and product_trends
        feature are both on. No writes.
    """
    if not bool(SettingsService.get(MODULE, 'enable_product_reports', default=True)):
        return False
    return product_trends_feature_enabled()


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _add_months(value: date, delta: int) -> date:
    month = value.month - 1 + delta
    year = value.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)


def _month_label(value: date) -> str:
    return f'{month_abbr[value.month]} {value.year}'


def _month_key(value: date) -> str:
    return f'{value.year:04d}-{value.month:02d}'


def build_product_trends(
    *,
    product_id: int,
    months: int = DEFAULT_MONTHS,
    variant_id: int | None = None,
    today: date | None = None,
) -> dict:
    """
    Monthly sold and received series for one product.

    Args:
        product_id: Positive product primary key.
        months: How many calendar months to include, 1–24. Out of range is
            clamped. Defaults to 12.
        variant_id: Optional variant id. When set, only that variant's lines
            and movements are counted. None means the whole product.
        today: Nairobi-facing calendar day for the window end. Defaults to
            ``timezone.localdate()``.

    Returns:
        dict: ``product_id``, optional ``variant_id``, ``months_requested``,
        ``months`` (oldest first, each with ``month``, ``label``,
        ``quantity_sold``, ``revenue``, ``order_count``, ``quantity_received``),
        ``channels`` (up to 8 client_channel slices for the window),
        ``summary`` (totals, best/worst month by quantity, averages).
        Empty product still returns zero-filled months. No writes.

    Raises:
        ValueError: When ``product_id`` is not a positive integer.
    """
    try:
        pid = int(product_id)
    except (TypeError, ValueError) as exc:
        raise ValueError('product_id must be a positive integer.') from exc
    if pid < 1:
        raise ValueError('product_id must be a positive integer.')

    try:
        span = int(months)
    except (TypeError, ValueError):
        span = DEFAULT_MONTHS
    span = max(1, min(MAX_MONTHS, span))

    vid = None
    if variant_id is not None and str(variant_id).strip() != '':
        try:
            vid = int(variant_id)
        except (TypeError, ValueError) as exc:
            raise ValueError('variant_id must be a positive integer.') from exc
        if vid < 1:
            raise ValueError('variant_id must be a positive integer.')

    end_day = today or timezone.localdate()
    end_month = _month_start(end_day)
    start_month = _add_months(end_month, -(span - 1))
    start_dt = timezone.make_aware(datetime.combine(start_month, time.min))
    # Exclusive end: first day of next month after end_month
    end_exclusive = _add_months(end_month, 1)
    end_dt = timezone.make_aware(datetime.combine(end_exclusive, time.min))

    sale_qs = posted_sale_items().filter(
        product_id=pid,
        sale__occurred_at__gte=start_dt,
        sale__occurred_at__lt=end_dt,
    )
    if vid is not None:
        sale_qs = sale_qs.filter(variant_id=vid)

    sold_rows = (
        sale_qs.annotate(bucket=TruncMonth('sale__occurred_at'))
        .values('bucket')
        .annotate(
            quantity_sold=Sum('quantity'),
            revenue=Sum('subtotal'),
            order_count=Count('sale_id', distinct=True),
        )
    )
    sold_by_month = {}
    for row in sold_rows:
        bucket = row['bucket']
        if bucket is None:
            continue
        key = _month_key(bucket.date() if hasattr(bucket, 'date') else bucket)
        sold_by_month[key] = {
            'quantity_sold': int(row['quantity_sold'] or 0),
            'revenue': Decimal(str(row['revenue'] or 0)).quantize(Decimal('0.01')),
            'order_count': int(row['order_count'] or 0),
        }

    channel_rows = (
        sale_qs.values('sale__client_channel')
        .annotate(quantity=Sum('quantity'))
        .order_by('-quantity')[:8]
    )
    channels = []
    for row in channel_rows:
        raw = (row['sale__client_channel'] or 'unknown').strip() or 'unknown'
        channels.append({
            'channel': raw[:40],
            'quantity': int(row['quantity'] or 0),
        })

    from inventory.models import StockMovement

    recv_qs = StockMovement.objects.filter(
        product_id=pid,
        movement_type='purchase',
        created_at__gte=start_dt,
        created_at__lt=end_dt,
    )
    if vid is not None:
        recv_qs = recv_qs.filter(variant_id=vid)
    recv_rows = (
        recv_qs.annotate(bucket=TruncMonth('created_at'))
        .values('bucket')
        .annotate(quantity_received=Sum('quantity'))
    )
    recv_by_month = {}
    for row in recv_rows:
        bucket = row['bucket']
        if bucket is None:
            continue
        key = _month_key(bucket.date() if hasattr(bucket, 'date') else bucket)
        recv_by_month[key] = int(row['quantity_received'] or 0)

    months = []
    cursor = start_month
    for _ in range(span):
        key = _month_key(cursor)
        sold = sold_by_month.get(key, {})
        months.append({
            'month': key,
            'label': _month_label(cursor),
            'quantity_sold': int(sold.get('quantity_sold') or 0),
            'revenue': f'{Decimal(sold.get("revenue") or 0):.2f}',
            'order_count': int(sold.get('order_count') or 0),
            'quantity_received': int(recv_by_month.get(key) or 0),
        })
        cursor = _add_months(cursor, 1)

    total_qty = sum(row['quantity_sold'] for row in months)
    total_revenue = sum(Decimal(row['revenue']) for row in months)
    total_orders = sum(row['order_count'] for row in months)
    total_received = sum(row['quantity_received'] for row in months)
    best = max(months, key=lambda row: row['quantity_sold']) if months else None
    worst = min(months, key=lambda row: row['quantity_sold']) if months else None
    avg_qty = round(total_qty / span, 2) if span else 0

    return {
        'product_id': pid,
        'variant_id': vid,
        'months_requested': span,
        'months': months,
        'channels': channels,
        'summary': {
            'quantity_sold': total_qty,
            'revenue': f'{total_revenue.quantize(Decimal("0.01")):.2f}',
            'order_count': total_orders,
            'quantity_received': total_received,
            'avg_monthly_quantity': avg_qty,
            'best_month': best['month'] if best and best['quantity_sold'] > 0 else '',
            'best_month_label': best['label'] if best and best['quantity_sold'] > 0 else '',
            'worst_month': worst['month'] if worst else '',
            'worst_month_label': worst['label'] if worst else '',
        },
    }
