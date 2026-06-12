"""Stock helpers when selling products with or without the variants feature.

Variant products store quantity on variant rows; parent ``stock_quantity`` is
kept in sync as the sum of active variants. Catalogue surfaces must use
``sellable_stock_quantity`` or ``apply_catalog_variant_representation``.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from django.db.models import Min, Sum

from settings.feature_flags import is_product_variants_enabled


def active_variant_stock_sum(product) -> int:
    """Total on-hand quantity across active variant rows."""
    if not product.has_variants:
        return 0
    total = product.variants.filter(is_active=True).aggregate(
        total=Sum('stock_quantity')
    )['total']
    return int(total or 0)


def sync_product_stock_from_variants(product) -> int:
    """
    Keep parent ``stock_quantity`` equal to the sum of active variant rows.
    Variant products never hold separate parent-only stock in reports/POS.
    """
    from products.models import Product

    if not product.has_variants or not product.track_stock:
        return int(product.stock_quantity or 0)
    total = active_variant_stock_sum(product)
    if int(product.stock_quantity or 0) != total:
        Product.objects.filter(pk=product.pk).update(stock_quantity=total)
        product.stock_quantity = total
    return total


def variants_sold_as_simple(product) -> bool:
    """True when the product has variants in DB but the feature is turned off."""
    return bool(product.has_variants and not is_product_variants_enabled())


def apply_catalog_variant_representation(product, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    When variants exist in DB but the feature is off, expose a simple sellable row:
    ``has_variants=False``, sellable stock, and min variant price when parent price is empty.
    """
    if not product.has_variants:
        return data
    variants = product.variants.filter(is_active=True)
    if not variants.exists() or is_product_variants_enabled():
        return data
    data = dict(data)
    data['has_variants'] = False
    data['stock_quantity'] = sellable_stock_quantity(product)
    agg = variants.aggregate(min_price=Min('price'))
    if (not data.get('price') or float(data.get('price') or 0) == 0) and agg.get('min_price'):
        data['price'] = str(agg['min_price'])
        if 'selling_price' in data or data.get('selling_price') is not None:
            data['selling_price'] = data['price']
    return data


def sellable_stock_quantity(product, variant=None) -> int:
    if variant is not None:
        return int(variant.stock_quantity or 0)
    if product.has_variants:
        return active_variant_stock_sum(product)
    return int(product.stock_quantity or 0)


def sellable_unit_price(product, variant=None, override=None) -> Decimal:
    """Selling price only — never MRP. Used for sale lines and revenue."""
    if override is not None:
        return Decimal(str(override))
    if variant is not None and variant.price is not None:
        return Decimal(str(variant.price))
    if product.price:
        return Decimal(str(product.price))
    if product.has_variants:
        min_price = product.variants.filter(is_active=True).aggregate(
            min_price=Min('price')
        )['min_price']
        if min_price is not None:
            return Decimal(str(min_price))
    return Decimal('0')


def sellable_unit_cost(product, variant=None) -> Decimal:
    if variant is not None and variant.cost is not None:
        return variant.cost
    return product.cost
