"""Past sale (backfill) validation and maker-checker policy."""

from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone


def backfill_requires_approval() -> bool:
    from approvals.permissions import is_maker_checker_enabled
    from settings.models import StoreSettings

    if not is_maker_checker_enabled():
        return False
    store = StoreSettings.load()
    return bool(getattr(store, 'backfill_maker_checker_enabled', True))


def backfill_max_days() -> int:
    from settings.models import StoreSettings

    store = StoreSettings.load()
    days = int(getattr(store, 'backfill_max_days', 30) or 30)
    return max(1, min(days, 365))


def validate_backfill_occurred_at(occurred_at) -> None:
    if occurred_at is None:
        raise ValidationError({'occurred_at': 'Sale date and time are required.'})
    now = timezone.now()
    if occurred_at > now + timedelta(minutes=5):
        raise ValidationError({'occurred_at': 'Sale date cannot be in the future.'})
    earliest = now - timedelta(days=backfill_max_days())
    if occurred_at < earliest:
        raise ValidationError(
            {
                'occurred_at': (
                    f'Sale date cannot be more than {backfill_max_days()} days in the past.'
                )
            }
        )


def validate_backfill_reason(reason: str) -> str:
    text = str(reason or '').strip()
    if len(text) < 10:
        raise ValidationError(
            {'backfill_reason': 'Please explain why this sale is being entered now (min 10 characters).'}
        )
    return text


def _product_ids_from_items(items) -> set[int]:
    ids: set[int] = set()
    for row in items or []:
        pid = row.get('product_id')
        if pid is not None and str(pid).strip() != '':
            ids.add(int(pid))
    return ids


def get_backfill_stock_warnings(occurred_at, items) -> list[dict]:
    """
    Warn when stock was counted/adjusted after the claimed sale date for any line product.
    """
    if occurred_at is None:
        return []

    from inventory.models import StockMovement
    from products.models import Product

    warnings: list[dict] = []
    for product_id in sorted(_product_ids_from_items(items)):
        product = Product.objects.filter(pk=product_id).only('id', 'name', 'track_stock').first()
        if not product or not product.track_stock:
            continue
        last_adj = (
            StockMovement.objects.filter(
                product_id=product_id,
                movement_type='adjustment',
                created_at__gte=occurred_at,
            )
            .order_by('-created_at')
            .first()
        )
        if not last_adj:
            continue
        when = timezone.localtime(last_adj.created_at).strftime('%Y-%m-%d %H:%M')
        warnings.append(
            {
                'product_id': product_id,
                'product_name': product.name,
                'last_adjustment_at': last_adj.created_at.isoformat(),
                'message': (
                    f'Stock for "{product.name}" was adjusted on {when} after this sale date. '
                    'Current stock may not match what was on hand when the sale happened.'
                ),
            }
        )
    return warnings


def backfill_stock_warnings_acknowledged(value) -> bool:
    return value in (True, 'true', 'True', '1', 1)


def validate_backfill_stock_warnings(occurred_at, items, *, acknowledged) -> list[dict]:
    warnings = get_backfill_stock_warnings(occurred_at, items)
    if warnings and not backfill_stock_warnings_acknowledged(acknowledged):
        raise ValidationError(
            {
                'stock_warnings': warnings,
                'error': (
                    'Stock was adjusted after this sale date for one or more products. '
                    'Review the warnings and confirm to continue.'
                ),
            }
        )
    return warnings
