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


def _item(*, sku, product_name, variant, category, quantity, unit_cost, unit_price) -> dict[str, Any]:
    qty = _qty(quantity)
    cost = Decimal(str(unit_cost or 0))
    price = Decimal(str(unit_price or 0))
    return {
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

        items.sort(key=lambda row: (row['item'].lower(), row['sku'], row['variant']))
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
