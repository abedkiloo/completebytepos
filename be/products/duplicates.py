"""Catch the same product being added twice."""

from __future__ import annotations

from products.models import Product


def normalize_product_name(name) -> str:
    return ' '.join(str(name or '').split())


def find_duplicate_product(name, *, exclude_id=None):
    normalized = normalize_product_name(name)
    if not normalized:
        return None
    qs = Product.objects.filter(name__iexact=normalized)
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    return qs.order_by('-is_active', 'id').first()


def duplicate_product_message(existing: Product) -> str:
    if existing.is_active:
        return (
            f'"{existing.name}" already exists (SKU {existing.sku}). '
            'Open that product and update it instead of adding it again.'
        )
    return (
        f'"{existing.name}" already exists but is inactive (SKU {existing.sku}). '
        'Reactivate it instead of adding it again.'
    )
