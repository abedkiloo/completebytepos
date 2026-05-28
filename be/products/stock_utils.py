"""Stock helpers when selling products with or without the variants feature."""

from decimal import Decimal
from typing import Optional, Tuple

from django.db.models import Min, Sum

from settings.feature_flags import is_product_variants_enabled


def variants_sold_as_simple(product) -> bool:
    """True when the product has variants in DB but the feature is turned off."""
    return bool(product.has_variants and not is_product_variants_enabled())


def sellable_stock_quantity(product, variant=None) -> int:
    if variant is not None:
        return variant.stock_quantity
    if product.has_variants:
        variant_total = product.variants.filter(is_active=True).aggregate(
            total=Sum('stock_quantity')
        )['total']
        variant_total = int(variant_total or 0)
        # Many catalogs keep quantity on the parent row, on variant rows, or
        # both. Taking the max avoids false "0 available" when the list/POS
        # shows parent stock but variants are empty (or vice versa).
        return max(int(product.stock_quantity or 0), variant_total)
    return product.stock_quantity


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
