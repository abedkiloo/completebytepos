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
MAX_COMPARE_PRODUCTS = 5  # primary + up to 4 peers
GRAIN_MONTH = 'month'
GRAIN_QUARTER = 'quarter'
VALID_GRAINS = frozenset({GRAIN_MONTH, GRAIN_QUARTER})


def parse_end_period(raw: str | None, grain: str) -> date | None:
    """
    Parse an explicit window end (month ``YYYY-MM`` or quarter ``YYYY-Qn``).

    Args:
        raw: End period string, or None/empty for “current”.
        grain: ``month`` or ``quarter``.

    Returns:
        A calendar date inside the chosen bucket (1st of month / quarter),
        or None when raw is empty.

    Raises:
        ValueError: When the format is invalid for the grain.
    """
    text = (raw or '').strip()
    if not text:
        return None
    grain_key = str(grain or GRAIN_MONTH).strip().lower()
    if grain_key == GRAIN_QUARTER:
        # YYYY-Qn
        if '-Q' in text.upper():
            parts = text.upper().replace(' ', '').split('-Q')
            if len(parts) != 2:
                raise ValueError('end must look like 2026-Q2 for quarters.')
            try:
                year = int(parts[0])
                q = int(parts[1])
            except ValueError as exc:
                raise ValueError('end must look like 2026-Q2 for quarters.') from exc
            if q < 1 or q > 4 or year < 2000 or year > 2100:
                raise ValueError('end quarter must be Q1–Q4 in years 2000–2100.')
            month = (q - 1) * 3 + 1
            return date(year, month, 1)
        raise ValueError('end must look like 2026-Q2 for quarters.')
    # Month: YYYY-MM or YYYY-MM-DD
    try:
        if len(text) >= 7 and text[4] == '-':
            year = int(text[0:4])
            month = int(text[5:7])
            if month < 1 or month > 12 or year < 2000 or year > 2100:
                raise ValueError
            return date(year, month, 1)
    except ValueError as exc:
        raise ValueError('end must look like 2026-03 for months.') from exc
    raise ValueError('end must look like 2026-03 for months.')


def parse_compare_product_ids(
    raw,
    *,
    primary_id: int,
    max_peers: int = MAX_COMPARE_PRODUCTS - 1,
) -> list[int]:
    """
    Parse peer product ids for multi-SKU compare (excludes primary).

    Args:
        raw: Comma-separated ids, list/tuple of ids, or None.
        primary_id: Primary product id (excluded from peers), ≥ 1.
        max_peers: Max other products, 1–4 typical (default 4).

    Returns:
        Deduped positive ints, length 0–max_peers, never including primary.

    Raises:
        ValueError: When any id is not a positive integer.
    """
    if raw in (None, '', []):
        return []
    if isinstance(raw, (list, tuple)):
        parts = list(raw)
    else:
        parts = str(raw).replace(' ', '').split(',')
    out: list[int] = []
    seen = {int(primary_id)}
    for part in parts:
        if part in (None, ''):
            continue
        try:
            pid = int(part)
        except (TypeError, ValueError) as exc:
            raise ValueError('compare_ids must be positive integers.') from exc
        if pid < 1:
            raise ValueError('compare_ids must be positive integers.')
        if pid in seen:
            continue
        seen.add(pid)
        out.append(pid)
        if len(out) >= max(0, int(max_peers)):
            break
    return out


def build_purchase_insights(
    *,
    periods: list[dict],
    summary: dict,
    grain: str,
    product_name: str = '',
) -> list[dict]:
    """
    Rule-based purchase / stock cues for the trends desk (senior-analyst style).

    Args:
        periods: Oldest-first period rows with quantity_sold / quantity_received.
        summary: Summary dict from ``build_product_trends``.
        grain: ``month`` or ``quarter``.
        product_name: Optional label for messages (max ~80 chars used).

    Returns:
        List of ``{severity, title, detail}`` (0–6 items). No writes.
    """
    if not periods:
        return []
    label = (product_name or 'This product').strip()[:80] or 'This product'
    period_word = 'quarter' if grain == GRAIN_QUARTER else 'month'
    sold = int(summary.get('quantity_sold') or 0)
    received = int(summary.get('quantity_received') or 0)
    tips: list[dict] = []

    if sold > 0 and received == 0:
        tips.append({
            'severity': 'reorder',
            'title': 'Sold with no stock receipts in window',
            'detail': (
                f'{label} moved {sold} units but received 0 in this window — '
                f'check open POs or plan the next purchase before stock-outs.'
            ),
        })
    elif received > 0 and sold == 0:
        tips.append({
            'severity': 'overstock',
            'title': 'Received but not selling',
            'detail': (
                f'{label} received {received} units with no sales in this window — '
                f'pause reorders and push sell-through first.'
            ),
        })
    elif received > 0 and sold > 0:
        ratio = sold / received
        if ratio >= 1.25:
            tips.append({
                'severity': 'reorder',
                'title': 'Demand ahead of receipts',
                'detail': (
                    f'{label} sold {sold} vs received {received} '
                    f'({ratio:.1f}×) — favour restocking this SKU next.'
                ),
            })
        elif ratio <= 0.5:
            tips.append({
                'severity': 'overstock',
                'title': 'Receipts ahead of demand',
                'detail': (
                    f'{label} sold {sold} vs received {received} — '
                    f'hold purchasing until the pile clears.'
                ),
            })

    if len(periods) >= 3:
        recent = [int(p.get('quantity_sold') or 0) for p in periods[-3:]]
        earlier = [int(p.get('quantity_sold') or 0) for p in periods[:-3]] or recent
        recent_avg = sum(recent) / len(recent)
        earlier_avg = sum(earlier) / len(earlier) if earlier else recent_avg
        if earlier_avg > 0 and recent_avg >= earlier_avg * 1.25:
            tips.append({
                'severity': 'rising',
                'title': f'Rising {period_word}ly demand',
                'detail': (
                    f'Recent average {recent_avg:.1f} units/{period_word} vs '
                    f'{earlier_avg:.1f} earlier — good candidate to buy more of next.'
                ),
            })
        elif earlier_avg > 0 and recent_avg <= earlier_avg * 0.65:
            tips.append({
                'severity': 'falling',
                'title': f'Cooling {period_word}ly demand',
                'detail': (
                    f'Recent average {recent_avg:.1f} vs earlier {earlier_avg:.1f} — '
                    f'trim the next purchase order for this SKU.'
                ),
            })

    best_label = (summary.get('best_period_label') or '').strip()
    if best_label and sold > 0:
        tips.append({
            'severity': 'peak',
            'title': f'Peak {period_word}',
            'detail': (
                f'Strongest {period_word} was {best_label} — align seasonal buys '
                f'and promotions around that pattern.'
            ),
        })

    return tips[:6]


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
    end: str | None = None,
    compare_ids=None,
) -> dict:
    """
    Period sales and receiving series for one product (optional multi-SKU compare).

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
        today: Calendar day for the window end when ``end`` is omitted.
            Defaults to ``timezone.localdate()``.
        end: Optional anchor period — ``YYYY-MM`` (month) or ``YYYY-Qn``
            (quarter). Trailing span ends on this bucket instead of “now”.
        compare_ids: Optional peer product ids (comma string or list), max 4,
            for multi-product line compare.

    Returns:
        dict: ``product_id``, optional ``variant_id``, ``grain``, ``end_period``,
        ``span_requested``, ``periods``, ``months``, ``channels``, ``summary``,
        ``variants`` / ``variant_series`` / ``variant_keys``, plus
        ``compare_keys`` / ``compare_series`` / ``compare_totals``, and
        ``insights`` (purchase cues). No writes.

    Raises:
        ValueError: When ids or ``end`` are invalid.
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

    end_anchor = parse_end_period(end, grain_key)
    peer_ids = parse_compare_product_ids(compare_ids, primary_id=pid)

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
        end_day = end_anchor or today or timezone.localdate()
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
        end_day = end_anchor or today or timezone.localdate()
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

    from products.models import Product as ProductModel

    primary_name = ''
    primary_row = (
        ProductModel.objects.filter(pk=pid).only('id', 'name', 'sku').first()
    )
    if primary_row is not None:
        primary_name = (primary_row.name or '')[:200]

    compare_keys = []
    compare_series = []
    compare_totals = []
    if peer_ids:
        peers = list(
            ProductModel.objects.filter(pk__in=peer_ids)
            .only('id', 'name', 'sku')
            .order_by('id')
        )
        peer_map = {p.pk: p for p in peers}
        ordered_peers = [peer_map[i] for i in peer_ids if i in peer_map]
        all_compare_ids = [pid] + [p.pk for p in ordered_peers]
        compare_keys = [
            {
                'product_id': pid,
                'label': (primary_name or f'Product {pid}')[:80],
                'sku': ((primary_row.sku if primary_row else '') or '')[:50],
                'key': f'p_{pid}',
                'is_primary': True,
            }
        ]
        for peer in ordered_peers:
            compare_keys.append({
                'product_id': peer.pk,
                'label': (peer.name or f'Product {peer.pk}')[:80],
                'sku': (peer.sku or '')[:50],
                'key': f'p_{peer.pk}',
                'is_primary': False,
            })

        period_product_qty: dict[str, dict[int, int]] = {}
        for row in (
            posted_sale_items()
            .filter(
                product_id__in=all_compare_ids,
                sale__occurred_at__gte=start_dt,
                sale__occurred_at__lt=end_dt,
            )
            .annotate(bucket=trunc_fn('sale__occurred_at'))
            .values('bucket', 'product_id')
            .annotate(quantity_sold=Sum('quantity'))
        ):
            bucket = row['bucket']
            if bucket is None or row['product_id'] is None:
                continue
            pkey = _bucket_key(bucket, grain_key)
            period_product_qty.setdefault(pkey, {})[row['product_id']] = int(
                row['quantity_sold'] or 0
            )

        for period_row in periods:
            point = {
                'period': period_row['period'],
                'label': period_row['label'],
            }
            bucket_map = period_product_qty.get(period_row['period'], {})
            for cid in all_compare_ids:
                point[f'p_{cid}'] = int(bucket_map.get(cid) or 0)
            compare_series.append(point)

        totals_by_id = {
            row['product_id']: {
                'quantity_sold': int(row['quantity_sold'] or 0),
                'revenue': Decimal(str(row['revenue'] or 0)).quantize(Decimal('0.01')),
            }
            for row in (
                posted_sale_items()
                .filter(
                    product_id__in=all_compare_ids,
                    sale__occurred_at__gte=start_dt,
                    sale__occurred_at__lt=end_dt,
                )
                .values('product_id')
                .annotate(
                    quantity_sold=Sum('quantity'),
                    revenue=Sum('subtotal'),
                )
            )
        }
        for key_row in compare_keys:
            tot = totals_by_id.get(key_row['product_id'], {})
            compare_totals.append({
                **key_row,
                'quantity_sold': int(tot.get('quantity_sold') or 0),
                'revenue': f'{Decimal(tot.get("revenue") or 0):.2f}',
            })
        compare_totals.sort(key=lambda row: (-row['quantity_sold'], row['label']))

    insights = build_purchase_insights(
        periods=periods,
        summary=summary,
        grain=grain_key,
        product_name=primary_name,
    )
    if compare_totals:
        leader = compare_totals[0]
        if leader['product_id'] != pid and leader['quantity_sold'] > 0:
            insights.insert(
                0,
                {
                    'severity': 'compare_leader',
                    'title': 'Stronger peer in this window',
                    'detail': (
                        f'{leader["label"]} outsold the primary SKU '
                        f'({leader["quantity_sold"]} units) — prefer that line '
                        f'for the next purchase if margins stay healthy.'
                    ),
                },
            )
            insights = insights[:6]

    return {
        'product_id': pid,
        'variant_id': vid,
        'grain': grain_key,
        'end_period': key_fn(end_bucket),
        'end_period_label': label_fn(end_bucket),
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
        'compare_ids': [k['product_id'] for k in compare_keys if not k.get('is_primary')],
        'compare_keys': compare_keys,
        'compare_series': compare_series,
        'compare_totals': compare_totals,
        'insights': insights,
    }
