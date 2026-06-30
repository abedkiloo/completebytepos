"""Queue past sale entries for maker-checker approval."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from approvals.service import submit_change
from approvals.registry import ACTION_SALE_BACKFILL
from sales.backfill_policy import backfill_requires_approval, validate_backfill_occurred_at, validate_backfill_reason


def sale_backfill_maker_checker_active() -> bool:
    return backfill_requires_approval()


def _summarize_items(items: list) -> str:
    parts = []
    for row in items or []:
        qty = row.get('quantity', 1)
        pid = row.get('product_id', '?')
        parts.append(f'product #{pid} × {qty}')
    return '; '.join(parts[:8]) if parts else '—'


def queue_sale_backfill(request, validated_data: Dict[str, Any]):
    if not sale_backfill_maker_checker_active():
        raise ValidationError('Maker-checker is not required for backfill.')

    occurred_at = validated_data.get('occurred_at')
    validate_backfill_occurred_at(occurred_at)
    reason = validate_backfill_reason(validated_data.get('backfill_reason', ''))

    items = validated_data.get('items') or []
    if not items:
        raise ValidationError({'items': 'At least one line item is required.'})

    served_by_id = validated_data.get('served_by_id')
    served_label = '—'
    if served_by_id:
        user = User.objects.filter(pk=served_by_id, is_active=True).first()
        if user:
            served_label = user.get_full_name().strip() or user.username

    total_hint = validated_data.get('_preview_total')
    summary = {
        'occurred_at': occurred_at.isoformat() if occurred_at else '',
        'sale_type': validated_data.get('sale_type', 'pos'),
        'customer_id': validated_data.get('customer_id'),
        'payment_method': validated_data.get('payment_method', 'cash'),
        'amount_paid': str(validated_data.get('amount_paid', 0)),
        'served_by': served_label,
        'lines': _summarize_items(items),
        'total': str(total_hint) if total_hint is not None else '—',
    }

    payload = {k: v for k, v in validated_data.items() if not k.startswith('_')}

    return submit_change(
        request=request,
        action_type=ACTION_SALE_BACKFILL,
        entity_type='sales.SaleBackfill',
        entity_id='new',
        entity_repr=f"Past sale {summary.get('occurred_at', '')[:10]}",
        original_values={},
        proposed_values=summary,
        reason=reason,
        apply_payload=payload,
    )
