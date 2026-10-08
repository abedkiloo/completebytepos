"""Current on-hand stock with cost and retail value."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Prefetch
from django.utils import timezone

from products.models import Product, ProductVariant
from products.status_rules import apply_operational_product_filter
from utils.document_branding import DEFAULT_CONTACT_PHONE, DEFAULT_TAGLINE, brand_name_line


def _qty(value) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _truthy(raw) -> bool:
    return str(raw or '').strip().lower() in ('1', 'true', 'yes', 'on')


def _variant_label(variant: ProductVariant) -> str:
    parts = []
    if variant.size_id and getattr(variant.size, 'name', None):
        parts.append(variant.size.name)
    if variant.color_id and getattr(variant.color, 'name', None):
        parts.append(variant.color.name)
    return ' / '.join(parts)


def _item(
    *,
    sku,
    product_name,
    variant,
    category,
    quantity,
    unit_cost,
    unit_price,
    layer_id=None,
    received_at=None,
) -> dict[str, Any]:
    qty = _qty(quantity)
    cost = Decimal(str(unit_cost or 0))
    price = Decimal(str(unit_price or 0))
    row = {
        'sku': sku or '',
        'item': product_name,
        'variant': variant or '',
        'category': category or '',
        'quantity': qty,
        'unit_cost': float(cost),
        'inventory_value': float((cost * qty).quantize(Decimal('0.01'))),
        'selling_price': float(price),
        'selling_value': float((price * qty).quantize(Decimal('0.01'))),
    }
    if layer_id is not None:
        row['layer_id'] = layer_id
    if received_at is not None:
        row['received_at'] = received_at
    return row


class StockValuationReportService:
    """Snapshot of what is in stock right now, valued at cost and selling price."""

    @staticmethod
    def build(request=None) -> dict[str, Any]:
        include_zero = False
        if request is not None:
            raw = request.query_params.get('include_zero')
            if raw is None and hasattr(request, 'GET'):
                raw = request.GET.get('include_zero')
            include_zero = _truthy(raw)

        from inventory.stock_layers import layers_enabled

        if layers_enabled():
            return StockValuationReportService._build_from_layers(
                include_zero=include_zero
            )

        variants_qs = ProductVariant.objects.select_related('size', 'color').filter(is_active=True)
        products = (
            apply_operational_product_filter(Product.objects.filter(track_stock=True))
            .select_related('category')
            .prefetch_related(Prefetch('variants', queryset=variants_qs))
            .order_by('name', 'sku')
        )

        items: list[dict[str, Any]] = []
        zero_stock_skus = 0
        for product in products:
            category = product.category.name if product.category_id else ''
            if product.has_variants:
                variants = list(product.variants.all())
                if variants:
                    for variant in variants:
                        row = _item(
                            sku=variant.sku or product.sku,
                            product_name=product.name,
                            variant=_variant_label(variant),
                            category=category,
                            quantity=variant.stock_quantity,
                            unit_cost=variant.effective_cost,
                            unit_price=variant.effective_price,
                        )
                        if row['quantity'] <= 0:
                            zero_stock_skus += 1
                            if not include_zero:
                                continue
                        items.append(row)
                    continue
            row = _item(
                sku=product.sku,
                product_name=product.name,
                variant='',
                category=category,
                quantity=product.stock_quantity,
                unit_cost=product.cost,
                unit_price=product.price,
            )
            if row['quantity'] <= 0:
                zero_stock_skus += 1
                if not include_zero:
                    continue
            items.append(row)

        return StockValuationReportService._finalize(
            items, include_zero=include_zero, zero_stock_skus=zero_stock_skus
        )

    @staticmethod
    def _build_from_layers(*, include_zero: bool) -> dict[str, Any]:
        """Value stock as sum of open layers (qty_remaining × unit_cost)."""
        from inventory.stock_layers import bulk_ensure_opening_layers, layer_stock_value_rows

        # One bulk pass (not per-SKU exists()) for any bare stock_quantity rows.
        bulk_ensure_opening_layers()

        items: list[dict[str, Any]] = []
        seen_skus: set[tuple] = set()
        for layer in layer_stock_value_rows():
            product = layer.product
            variant = layer.variant
            category = product.category.name if product.category_id else ''
            variant_label = _variant_label(variant) if variant else ''
            sku = (variant.sku if variant and variant.sku else product.sku) or ''
            seen_skus.add((product.id, variant.id if variant else None))
            items.append(
                _item(
                    sku=sku,
                    product_name=product.name,
                    variant=variant_label,
                    category=category,
                    quantity=layer.qty_remaining,
                    unit_cost=layer.unit_cost,
                    unit_price=layer.unit_sell_price,
                    layer_id=layer.id,
                    received_at=(
                        layer.received_at.isoformat() if layer.received_at else None
                    ),
                )
            )

        zero_stock_skus = 0
        variants_qs = ProductVariant.objects.select_related('size', 'color').filter(
            is_active=True
        )
        catalog_products = (
            apply_operational_product_filter(Product.objects.filter(track_stock=True))
            .select_related('category')
            .prefetch_related(Prefetch('variants', queryset=variants_qs))
        )
        for product in catalog_products:
            category = product.category.name if product.category_id else ''
            if product.has_variants:
                variants = list(product.variants.all())
                if variants:
                    for variant in variants:
                        key = (product.id, variant.id)
                        if key in seen_skus:
                            continue
                        if _qty(variant.stock_quantity) > 0:
                            continue
                        zero_stock_skus += 1
                        if include_zero:
                            items.append(
                                _item(
                                    sku=variant.sku or product.sku,
                                    product_name=product.name,
                                    variant=_variant_label(variant),
                                    category=category,
                                    quantity=0,
                                    unit_cost=variant.effective_cost,
                                    unit_price=variant.effective_price,
                                )
                            )
                    continue
            key = (product.id, None)
            if key in seen_skus:
                continue
            if _qty(product.stock_quantity) > 0:
                continue
            zero_stock_skus += 1
            if include_zero:
                items.append(
                    _item(
                        sku=product.sku,
                        product_name=product.name,
                        variant='',
                        category=category,
                        quantity=0,
                        unit_cost=product.cost,
                        unit_price=product.price,
                    )
                )

        return StockValuationReportService._finalize(
            items,
            include_zero=include_zero,
            zero_stock_skus=zero_stock_skus,
            by_layer=True,
        )

    @staticmethod
    def _finalize(
        items: list[dict[str, Any]],
        *,
        include_zero: bool,
        zero_stock_skus: int,
        by_layer: bool = False,
    ) -> dict[str, Any]:
        items.sort(
            key=lambda row: (
                row['item'].lower(),
                row['sku'],
                row['variant'],
                row.get('received_at') or '',
            )
        )
        inventory_value = round(sum(row['inventory_value'] for row in items), 2)
        selling_value = round(sum(row['selling_value'] for row in items), 2)
        owner = brand_name_line()
        as_of = timezone.now().isoformat()
        return {
            'generated_at': as_of,
            'as_of': as_of,
            'owner': owner,
            'tagline': DEFAULT_TAGLINE,
            'contact': f'Tel: {DEFAULT_CONTACT_PHONE}',
            'include_zero': include_zero,
            'by_layer': by_layer,
            'summary': {
                'owner': owner,
                'item_count': len(items),
                'units_on_hand': sum(row['quantity'] for row in items),
                'inventory_value': inventory_value,
                'selling_value': selling_value,
                'zero_stock_skus': zero_stock_skus,
            },
            'items': items,
        }
