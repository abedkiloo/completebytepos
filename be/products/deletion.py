"""Permanent product deletion: admin only, for items added in error.

A product can only be removed when nothing real depends on it — no stock on
hand and no sales, invoices, refunds, deliveries, agent stock or real stock
events. Stock corrections (adjustments, damage, waste, expiry) on a product
that never traded are removed with it.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum

ADMIN_ONLY_DELETE_MESSAGE = (
    'Only an admin can permanently delete products. Deactivate it instead.'
)

# Reverse relations removed together with the product.
_CLEARED_WITH_PRODUCT = {'variants', 'stock_movements'}
_TRADING_MOVEMENT_TYPES = ('sale', 'purchase', 'return', 'transfer')


def require_product_delete_admin(user) -> None:
    from approvals.permissions import user_has_admin_checker_override

    if not user_has_admin_checker_override(user):
        raise PermissionDenied(ADMIN_ONLY_DELETE_MESSAGE)


def _stock_on_hand(product) -> int:
    variant_stock = product.variants.aggregate(total=Sum('stock_quantity'))['total'] or 0
    return max(int(product.stock_quantity or 0), int(variant_stock))


def product_delete_blockers(product) -> list[str]:
    """Plain-language reasons this product cannot be permanently deleted."""
    blockers: list[str] = []
    on_hand = _stock_on_hand(product)
    if on_hand > 0:
        blockers.append(f'it still has {on_hand} in stock')

    for rel in product._meta.related_objects:
        if rel.many_to_many or rel.get_accessor_name() in _CLEARED_WITH_PRODUCT:
            continue
        model = rel.related_model
        if model.objects.filter(**{rel.field.name: product}).exists():
            blockers.append(f'it is used in {model._meta.verbose_name_plural}')

    if product.stock_movements.filter(movement_type__in=_TRADING_MOVEMENT_TYPES).exists():
        blockers.append('it has sales, purchases, returns or transfers in its stock history')
    return blockers


def product_delete_blocked_message(product, blockers: list[str]) -> str:
    return (
        f'"{product.name}" cannot be deleted because {"; ".join(blockers)}. '
        'Deactivate it instead.'
    )


def assert_product_deletable(product) -> None:
    blockers = product_delete_blockers(product)
    if blockers:
        raise ValidationError(product_delete_blocked_message(product, blockers))


def permanently_delete_product(product) -> None:
    with transaction.atomic():
        from products.models import Product

        locked = Product.objects.select_for_update().get(pk=product.pk)
        assert_product_deletable(locked)
        locked.delete()
