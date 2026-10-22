"""Low-stock and out-of-stock rules for simple products and variant rows."""

from __future__ import annotations

from django.db.models import Exists, F, OuterRef, Q, QuerySet
from django.db.models.functions import Coalesce

from products.models import Product, ProductVariant


def variant_effective_threshold(variant) -> int:
    if variant.low_stock_threshold is not None:
        return int(variant.low_stock_threshold)
    return int(variant.product.low_stock_threshold or 0)


def variant_is_out_of_stock(variant) -> bool:
    return bool(variant.is_active) and int(variant.stock_quantity or 0) <= 0


def variant_is_low_stock(variant) -> bool:
    qty = int(variant.stock_quantity or 0)
    if qty <= 0:
        return False
    return qty <= variant_effective_threshold(variant)


def product_has_out_of_stock(product) -> bool:
    if not product.track_stock:
        return False
    if product.has_variants:
        variants = getattr(product, '_prefetched_objects_cache', {}).get('variants')
        if variants is not None:
            return any(variant_is_out_of_stock(v) for v in variants)
        return ProductVariant.objects.filter(
            product=product,
            is_active=True,
            stock_quantity=0,
        ).exists()
    return int(product.stock_quantity or 0) <= 0


def product_has_low_stock(product) -> bool:
    if not product.track_stock:
        return False
    if product.has_variants:
        variants = getattr(product, '_prefetched_objects_cache', {}).get('variants')
        if variants is not None:
            return any(variant_is_low_stock(v) for v in variants)
        low_variants = ProductVariant.objects.filter(
            product=product,
            is_active=True,
            stock_quantity__gt=0,
        ).annotate(
            effective_threshold=Coalesce('low_stock_threshold', 'product__low_stock_threshold')
        ).filter(stock_quantity__lte=F('effective_threshold'))
        return low_variants.exists()
    qty = int(product.stock_quantity or 0)
    if qty <= 0:
        return False
    return qty <= int(product.low_stock_threshold or 0)


def _active_variant_qs(product_ids=None):
    qs = ProductVariant.objects.filter(
        is_active=True,
        product__track_stock=True,
        product__has_variants=True,
    )
    if product_ids is not None:
        qs = qs.filter(product_id__in=product_ids)
    return qs


def count_stock_alert_items(product_queryset: QuerySet | None = None) -> dict[str, int]:
    """Count alert rows: simple products plus individual variant rows."""
    products = product_queryset if product_queryset is not None else Product.objects.all()

    simple_low = products.filter(
        track_stock=True,
        has_variants=False,
        stock_quantity__gt=0,
        stock_quantity__lte=F('low_stock_threshold'),
    ).count()
    simple_oos = products.filter(
        track_stock=True,
        has_variants=False,
        stock_quantity=0,
    ).count()

    product_ids = products.values('pk')
    variant_qs = _active_variant_qs(product_ids=product_ids)
    variant_low = (
        variant_qs.filter(stock_quantity__gt=0)
        .annotate(
            effective_threshold=Coalesce('low_stock_threshold', 'product__low_stock_threshold')
        )
        .filter(stock_quantity__lte=F('effective_threshold'))
        .count()
    )
    variant_oos = variant_qs.filter(stock_quantity=0).count()

    return {
        'low_stock_count': simple_low + variant_low,
        'out_of_stock_count': simple_oos + variant_oos,
        'low_stock_simple_count': simple_low,
        'low_stock_variant_count': variant_low,
        'out_of_stock_simple_count': simple_oos,
        'out_of_stock_variant_count': variant_oos,
    }


def apply_low_stock_filter(queryset: QuerySet) -> QuerySet:
    low_variants = ProductVariant.objects.filter(
        product_id=OuterRef('pk'),
        is_active=True,
        stock_quantity__gt=0,
    ).annotate(
        effective_threshold=Coalesce('low_stock_threshold', 'product__low_stock_threshold')
    ).filter(stock_quantity__lte=F('effective_threshold'))

    simple = Q(
        has_variants=False,
        track_stock=True,
        stock_quantity__gt=0,
        stock_quantity__lte=F('low_stock_threshold'),
    )
    with_variants = Q(has_variants=True, track_stock=True) & Exists(low_variants)
    return queryset.filter(simple | with_variants)


def apply_out_of_stock_filter(queryset: QuerySet) -> QuerySet:
    empty_variants = ProductVariant.objects.filter(
        product_id=OuterRef('pk'),
        is_active=True,
        stock_quantity=0,
    )
    simple = Q(has_variants=False, track_stock=True, stock_quantity=0)
    with_variants = Q(has_variants=True, track_stock=True) & Exists(empty_variants)
    return queryset.filter(simple | with_variants)


def _variant_display_label(variant) -> str:
    parts = []
    size = getattr(variant, 'size', None)
    color = getattr(variant, 'color', None)
    if size and getattr(size, 'name', None):
        parts.append(size.name)
    if color and getattr(color, 'name', None):
        parts.append(color.name)
    if parts:
        return ' / '.join(parts)
    return variant.sku or f'Variant #{variant.pk}'


def list_stock_alert_items(*, kind: str = 'out_of_stock') -> list[dict]:
    """
    Flat alert rows for inventory UI.

    Simple products appear as one row. Variant products contribute **only** the
    matching variant rows (never a parent total).
    """
    kind = (kind or 'out_of_stock').strip().lower()
    items: list[dict] = []

    simple_qs = Product.objects.filter(
        is_active=True,
        track_stock=True,
        has_variants=False,
    ).order_by('name')
    if kind == 'out_of_stock':
        simple_qs = simple_qs.filter(stock_quantity=0)
    else:
        # low_stock + needs_reorder
        simple_qs = simple_qs.filter(
            stock_quantity__gt=0,
            stock_quantity__lte=F('low_stock_threshold'),
        )
    for product in simple_qs:
        items.append(
            {
                'id': f'product-{product.id}',
                'kind': 'product',
                'product_id': product.id,
                'variant_id': None,
                'name': product.name,
                'sku': product.sku,
                'stock_quantity': int(product.stock_quantity or 0),
                'low_stock_threshold': int(product.low_stock_threshold or 0),
                'has_variants': False,
                'variant_label': None,
            }
        )

    variant_qs = (
        ProductVariant.objects.filter(
            is_active=True,
            product__is_active=True,
            product__track_stock=True,
            product__has_variants=True,
        )
        .select_related('product', 'size', 'color')
        .order_by('product__name', 'id')
    )
    if kind == 'out_of_stock':
        variant_qs = variant_qs.filter(stock_quantity=0)
    else:
        variant_qs = (
            variant_qs.filter(stock_quantity__gt=0)
            .annotate(
                effective_threshold=Coalesce(
                    'low_stock_threshold', 'product__low_stock_threshold'
                )
            )
            .filter(stock_quantity__lte=F('effective_threshold'))
        )

    for variant in variant_qs:
        label = _variant_display_label(variant)
        threshold = variant_effective_threshold(variant)
        items.append(
            {
                'id': f'variant-{variant.id}',
                'kind': 'variant',
                'product_id': variant.product_id,
                'variant_id': variant.id,
                'name': f'{variant.product.name} · {label}',
                'sku': variant.sku or variant.product.sku,
                'stock_quantity': int(variant.stock_quantity or 0),
                'low_stock_threshold': threshold,
                'has_variants': True,
                'variant_label': label,
            }
        )
    return items
