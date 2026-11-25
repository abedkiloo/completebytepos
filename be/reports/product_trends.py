"""
Per-product sales and receiving trends for the product detail desk.

Staff open any product (not only top sellers) and view month or quarter
performance, optionally scoped to one variant or compared across variants.
"""

from __future__ import annotations

from calendar import month_abbr
from datetime import date, datetime, time
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth, TruncQuarter
from django.utils import timezone

from reports.sale_scope import posted_sale_items
from settings.module_features import is_module_feature_enabled
from settings.settings_service import SettingsService

MODULE = 'reports'
MAX_MONTHS = 24
DEFAULT_MONTHS = 12
MAX_QUARTERS = 8
DEFAULT_QUARTERS = 4
MAX_VARIANTS_COMPARE = 12
GRAIN_MONTH = 'month'
GRAIN_QUARTER = 'quarter'
VALID_GRAINS = frozenset({GRAIN_MONTH, GRAIN_QUARTER})


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


def _quarter_start(value: date) -> date:
    month = ((value.month - 1) // 3) * 3 + 1
    return date(value.year, month, 1)


def _add_months(value: date, delta: int) -> date:
    month = value.month - 1 + delta
    year = value.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)


def _add_quarters(value: date, delta: int) -> date:
    return _add_months(_quarter_start(value), delta * 3)


def _month_label(value: date) -> str:
    return f'{month_abbr[value.month]} {value.year}'


def _quarter_label(value: date) -> str:
    q = (value.month - 1) // 3 + 1
    return f'Q{q} {value.year}'


def _month_key(value: date) -> str:
    return f'{value.year:04d}-{value.month:02d}'


def _quarter_key(value: date) -> str:
    q = (value.month - 1) // 3 + 1
    return f'{value.year:04d}-Q{q}'


def _bucket_key(bucket, grain: str) -> str:
    day = bucket.date() if hasattr(bucket, 'date') else bucket
    if grain == GRAIN_QUARTER:
        return _quarter_key(day)
    return _month_key(day)


def _variant_label(variant) -> str:
    parts = []
    size = getattr(variant, 'size', None)
    color = getattr(variant, 'color', None)
    if size is not None and getattr(size, 'name', None):
        parts.append(str(size.name)[:40])
    if color is not None and getattr(color, 'name', None):
        parts.append(str(color.name)[:40])
    if parts:
        return ' / '.join(parts)[:80]
    sku = (getattr(variant, 'sku', None) or '').strip()
    return sku[:80] if sku else f'Variant {variant.pk}'


def _empty_sold() -> dict:
    return {
        'quantity_sold': 0,
        'revenue': Decimal('0.00'),
        'order_count': 0,
    }


def _aggregate_by_bucket(qs, trunc_fn, date_field: str, grain: str) -> dict:
    rows = (
        qs.annotate(bucket=trunc_fn(date_field))
        .values('bucket')
        .annotate(
            quantity_sold=Sum('quantity'),
            revenue=Sum('subtotal'),
            order_count=Count('sale_id', distinct=True),
        )
    )
    out = {}
    for row in rows:
        bucket = row['bucket']
        if bucket is None:
            continue
        key = _bucket_key(bucket, grain)
        out[key] = {
            'quantity_sold': int(row['quantity_sold'] or 0),
            'revenue': Decimal(str(row['revenue'] or 0)).quantize(Decimal('0.01')),
            'order_count': int(row['order_count'] or 0),
        }
    return out


def _received_by_bucket(qs, trunc_fn, grain: str) -> dict:
    rows = (
        qs.annotate(bucket=trunc_fn('created_at'))
        .values('bucket')
        .annotate(quantity_received=Sum('quantity'))
    )
    out = {}
    for row in rows:
        bucket = row['bucket']
        if bucket is None:
            continue
        key = _bucket_key(bucket, grain)
        out[key] = int(row['quantity_received'] or 0)
    return out


def build_product_trends(
    *,
    product_id: int,
    months: int = DEFAULT_MONTHS,
    quarters: int | None = None,
    grain: str = GRAIN_MONTH,
    variant_id: int | None = None,
    include_variants: bool = True,
    today: date | None = None,
) -> dict:
    """
    Period sales and receiving series for one product.

    Args:
        product_id: Positive product primary key.
        months: Calendar months when ``grain`` is month, 1–24. Clamped.
            Defaults to 12. Ignored when ``grain`` is quarter unless
            ``quarters`` is omitted (then months/3, min 1).
        quarters: Calendar quarters when ``grain`` is quarter, 1–8.
            Defaults to 4 when omitted.
        grain: ``month`` or ``quarter``. Invalid values fall back to month.
        variant_id: Optional variant id. When set, only that variant's lines
            and movements are counted and variant compare is skipped.
        include_variants: When True and the product has variants and no
            ``variant_id``, include per-variant totals and a compare series
            (up to 12 variants). Defaults True.
        today: Calendar day for the window end. Defaults to
            ``timezone.localdate()``.

    Returns:
        dict: ``product_id``, optional ``variant_id``, ``grain``,
        ``span_requested``, ``periods`` (oldest first: ``period``, ``label``,
        ``quantity_sold``, ``revenue``, ``order_count``, ``quantity_received``),
        ``months`` (same as ``periods`` when grain is month, else []),
        ``channels``, ``summary``, ``variants`` (compare totals),
        ``variant_series`` (period rows with ``v_<id>`` qty keys),
        ``variant_keys`` (id/label/key for charts). Empty product still
        returns zero-filled periods. No writes.

    Raises:
        ValueError: When ``product_id`` or ``variant_id`` is not a positive
            integer.
    """
    try:
        pid = int(product_id)
    except (TypeError, ValueError) as exc:
        raise ValueError('product_id must be a positive integer.') from exc
    if pid < 1:
        raise ValueError('product_id must be a positive integer.')

    grain_key = str(grain or GRAIN_MONTH).strip().lower()
    if grain_key not in VALID_GRAINS:
        grain_key = GRAIN_MONTH

    vid = None
    if variant_id is not None and str(variant_id).strip() != '':
        try:
            vid = int(variant_id)
        except (TypeError, ValueError) as exc:
            raise ValueError('variant_id must be a positive integer.') from exc
        if vid < 1:
            raise ValueError('variant_id must be a positive integer.')

    if grain_key == GRAIN_QUARTER:
        if quarters is None:
            try:
                months_hint = int(months)
            except (TypeError, ValueError):
                months_hint = DEFAULT_MONTHS
            span = max(1, min(MAX_QUARTERS, (max(1, months_hint) + 2) // 3))
        else:
            try:
                span = int(quarters)
            except (TypeError, ValueError):
                span = DEFAULT_QUARTERS
            span = max(1, min(MAX_QUARTERS, span))
        trunc_fn = TruncQuarter
        end_day = today or timezone.localdate()
        end_bucket = _quarter_start(end_day)
        start_bucket = _add_quarters(end_bucket, -(span - 1))
        label_fn = _quarter_label
        key_fn = _quarter_key
        step_fn = _add_quarters
        end_exclusive = _add_quarters(end_bucket, 1)
    else:
        try:
            span = int(months)
        except (TypeError, ValueError):
            span = DEFAULT_MONTHS
        span = max(1, min(MAX_MONTHS, span))
        trunc_fn = TruncMonth
        end_day = today or timezone.localdate()
        end_bucket = _month_start(end_day)
        start_bucket = _add_months(end_bucket, -(span - 1))
        label_fn = _month_label
        key_fn = _month_key
        step_fn = _add_months
        end_exclusive = _add_months(end_bucket, 1)

    start_dt = timezone.make_aware(datetime.combine(start_bucket, time.min))
    end_dt = timezone.make_aware(datetime.combine(end_exclusive, time.min))

    sale_qs = posted_sale_items().filter(
        product_id=pid,
        sale__occurred_at__gte=start_dt,
        sale__occurred_at__lt=end_dt,
    )
    if vid is not None:
        sale_qs = sale_qs.filter(variant_id=vid)

    sold_by = _aggregate_by_bucket(sale_qs, trunc_fn, 'sale__occurred_at', grain_key)

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
    recv_by = _received_by_bucket(recv_qs, trunc_fn, grain_key)

    periods = []
    cursor = start_bucket
    for _ in range(span):
        key = key_fn(cursor)
        sold = sold_by.get(key, _empty_sold())
        periods.append({
            'period': key,
            'month': key if grain_key == GRAIN_MONTH else '',
            'label': label_fn(cursor),
            'quantity_sold': int(sold.get('quantity_sold') or 0),
            'revenue': f'{Decimal(sold.get("revenue") or 0):.2f}',
            'order_count': int(sold.get('order_count') or 0),
            'quantity_received': int(recv_by.get(key) or 0),
        })
        cursor = step_fn(cursor, 1)

    total_qty = sum(row['quantity_sold'] for row in periods)
    total_revenue = sum(Decimal(row['revenue']) for row in periods)
    total_orders = sum(row['order_count'] for row in periods)
    total_received = sum(row['quantity_received'] for row in periods)
    best = max(periods, key=lambda row: row['quantity_sold']) if periods else None
    worst = min(periods, key=lambda row: row['quantity_sold']) if periods else None
    avg_qty = round(total_qty / span, 2) if span else 0

    variants_out = []
    variant_keys = []
    variant_series = []

    if include_variants and vid is None:
        from products.models import ProductVariant

        variant_rows = list(
            ProductVariant.objects.filter(product_id=pid)
            .select_related('size', 'color')
            .order_by('id')[:MAX_VARIANTS_COMPARE]
        )
        if variant_rows:
            variant_ids = [v.pk for v in variant_rows]
            sold_by_variant = {
                row['variant_id']: {
                    'quantity_sold': int(row['quantity_sold'] or 0),
                    'revenue': Decimal(str(row['revenue'] or 0)).quantize(
                        Decimal('0.01')
                    ),
                    'order_count': int(row['order_count'] or 0),
                }
                for row in (
                    posted_sale_items()
                    .filter(
                        product_id=pid,
                        variant_id__in=variant_ids,
                        sale__occurred_at__gte=start_dt,
                        sale__occurred_at__lt=end_dt,
                    )
                    .values('variant_id')
                    .annotate(
                        quantity_sold=Sum('quantity'),
                        revenue=Sum('subtotal'),
                        order_count=Count('sale_id', distinct=True),
                    )
                )
            }
            recv_by_variant = {
                row['variant_id']: int(row['quantity_received'] or 0)
                for row in (
                    StockMovement.objects.filter(
                        product_id=pid,
                        variant_id__in=variant_ids,
                        movement_type='purchase',
                        created_at__gte=start_dt,
                        created_at__lt=end_dt,
                    )
                    .values('variant_id')
                    .annotate(quantity_received=Sum('quantity'))
                )
            }

            period_variant_qty = {}
            for row in (
                posted_sale_items()
                .filter(
                    product_id=pid,
                    variant_id__in=variant_ids,
                    sale__occurred_at__gte=start_dt,
                    sale__occurred_at__lt=end_dt,
                )
                .annotate(bucket=trunc_fn('sale__occurred_at'))
                .values('bucket', 'variant_id')
                .annotate(quantity_sold=Sum('quantity'))
            ):
                bucket = row['bucket']
                if bucket is None or row['variant_id'] is None:
                    continue
                pkey = _bucket_key(bucket, grain_key)
                period_variant_qty.setdefault(pkey, {})[row['variant_id']] = int(
                    row['quantity_sold'] or 0
                )

            for variant in variant_rows:
                label = _variant_label(variant)
                chart_key = f'v_{variant.pk}'
                sold = sold_by_variant.get(variant.pk, _empty_sold())
                variants_out.append({
                    'variant_id': variant.pk,
                    'label': label,
                    'sku': (variant.sku or '')[:50],
                    'chart_key': chart_key,
                    'quantity_sold': int(sold.get('quantity_sold') or 0),
                    'revenue': f'{Decimal(sold.get("revenue") or 0):.2f}',
                    'order_count': int(sold.get('order_count') or 0),
                    'quantity_received': int(recv_by_variant.get(variant.pk) or 0),
                })
                variant_keys.append({
                    'variant_id': variant.pk,
                    'label': label,
                    'key': chart_key,
                })

            variants_out.sort(
                key=lambda row: (-row['quantity_sold'], row['label'])
            )

            for period_row in periods:
                point = {
                    'period': period_row['period'],
                    'label': period_row['label'],
                }
                bucket_map = period_variant_qty.get(period_row['period'], {})
                for variant in variant_rows:
                    point[f'v_{variant.pk}'] = int(bucket_map.get(variant.pk) or 0)
                variant_series.append(point)

    summary = {
        'quantity_sold': total_qty,
        'revenue': f'{total_revenue.quantize(Decimal("0.01")):.2f}',
        'order_count': total_orders,
        'quantity_received': total_received,
        'avg_period_quantity': avg_qty,
        'avg_monthly_quantity': avg_qty if grain_key == GRAIN_MONTH else round(
            total_qty / max(1, span * 3), 2
        ),
        'best_period': best['period'] if best and best['quantity_sold'] > 0 else '',
        'best_period_label': best['label'] if best and best['quantity_sold'] > 0 else '',
        'worst_period': worst['period'] if worst else '',
        'worst_period_label': worst['label'] if worst else '',
        # Month aliases kept for older clients.
        'best_month': best['period']
        if grain_key == GRAIN_MONTH and best and best['quantity_sold'] > 0
        else '',
        'best_month_label': best['label']
        if grain_key == GRAIN_MONTH and best and best['quantity_sold'] > 0
        else '',
        'worst_month': worst['period'] if grain_key == GRAIN_MONTH and worst else '',
        'worst_month_label': worst['label'] if grain_key == GRAIN_MONTH and worst else '',
    }

    return {
        'product_id': pid,
        'variant_id': vid,
        'grain': grain_key,
        'span_requested': span,
        'months_requested': span if grain_key == GRAIN_MONTH else 0,
        'quarters_requested': span if grain_key == GRAIN_QUARTER else 0,
        'periods': periods,
        'months': periods if grain_key == GRAIN_MONTH else [],
        'channels': channels,
        'summary': summary,
        'variants': variants_out,
        'variant_keys': variant_keys,
        'variant_series': variant_series,
    }
