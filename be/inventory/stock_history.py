"""Product stock history trail (debt-ledger style) + admin access gates."""

from __future__ import annotations

from typing import Any

from inventory.access import product_stock_history_feature_allowed


MOVEMENT_CHANGE_LABELS = {
    'sale': 'Sold',
    'purchase': 'Received',
    'adjustment': 'Adjusted',
    'return': 'Returned',
    'damage': 'Damaged',
    'transfer': 'Transferred',
    'waste': 'Wasted',
    'expired': 'Expired',
}


def user_is_stock_history_admin(user) -> bool:
    """Only store admins / managers / super-admins see full product stock history."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    return bool(
        getattr(profile, 'is_super_admin', False)
        or getattr(profile, 'is_admin', False)
        or getattr(profile, 'is_manager', False)
    )


def product_stock_history_allowed(user) -> bool:
    """Config on + admin persona."""
    if not product_stock_history_feature_allowed():
        return False
    return user_is_stock_history_admin(user)


def movement_user_display(user) -> str:
    if user is None:
        return ''
    full = (user.get_full_name() or '').strip()
    if full:
        return full
    return user.username or ''


def stock_flow_for_movement(movement) -> dict[str, Any]:
    """
    Mirror debt trail: previous → change → new.

    Example: Previous stock 400 · Sold 45 · New stock 355 · by User K
    """
    before = int(getattr(movement, 'stock_before', 0) or 0)
    after = int(getattr(movement, 'stock_after', 0) or 0)
    delta = int(movement._stock_delta()) if hasattr(movement, '_stock_delta') else (after - before)
    mtype = getattr(movement, 'movement_type', '') or ''
    verb = MOVEMENT_CHANGE_LABELS.get(mtype, mtype.replace('_', ' ').title() or 'Changed')
    abs_qty = abs(delta)

    if mtype == 'adjustment':
        change_label = f'Adjusted {delta:+d}'
    elif delta < 0 and mtype not in ('sale', 'damage', 'waste', 'expired', 'transfer'):
        change_label = f'{verb} {abs_qty}'
    else:
        change_label = f'{verb} {abs_qty}'

    user_name = movement_user_display(getattr(movement, 'user', None))
    parts = [
        f'Previous stock {before}',
        change_label,
        f'New stock {after}',
    ]
    if user_name:
        parts.append(f'by {user_name}')

    return {
        'previous_stock': before,
        'change_qty': delta,
        'new_stock': after,
        'change_label': change_label,
        'stock_flow': ' · '.join(parts),
        'user_display': user_name,
    }


def serialize_stock_history_entry(movement, base: dict | None = None) -> dict:
    """Merge serializer payload with trail fields."""
    data = dict(base or {})
    trail = stock_flow_for_movement(movement)
    data.update(trail)
    if trail.get('user_display'):
        data['user_name'] = trail['user_display']
    return data


def record_opening_stock_movement(*, product, user=None, branch=None):
    """
    When a product is created with an initial on-hand qty, write a purchase
    movement so the admin ledger starts at insertion (Previous 0 · Received N).

    Resets stock to 0 then applies the movement so StockMovement.save() does
    not double-count the quantity already stored on Product.
    """
    from django.db import transaction
    from inventory.models import StockMovement
    from products.models import Product

    if product is None or not getattr(product, 'track_stock', True):
        return None
    if getattr(product, 'has_variants', False):
        return None
    opening = int(getattr(product, 'stock_quantity', 0) or 0)
    if opening <= 0:
        return None
    if StockMovement.objects.filter(product_id=product.pk, reference='OPENING').exists():
        return None

    with transaction.atomic():
        Product.objects.filter(pk=product.pk).update(stock_quantity=0)
        product.stock_quantity = 0
        return StockMovement.objects.create(
            branch=branch,
            product=product,
            movement_type='purchase',
            quantity=opening,
            unit_cost=getattr(product, 'cost', None) or None,
            reference='OPENING',
            notes='Opening stock when product was added to the system',
            user=user,
        )
