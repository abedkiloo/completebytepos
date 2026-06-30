"""Queue past sale entries for maker-checker approval."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from approvals.models import PendingChange
from approvals.service import submit_change, _json_safe
from approvals.registry import ACTION_SALE_BACKFILL
from sales.backfill_policy import (
    backfill_requires_approval,
    validate_backfill_occurred_at,
    validate_backfill_reason,
    resolve_backfill_served_by,
)


def sale_backfill_maker_checker_active() -> bool:
    return backfill_requires_approval()


def _summarize_items(items: list) -> str:
    parts = []
    for row in items or []:
        qty = row.get('quantity', 1)
        pid = row.get('product_id', '?')
        vid = row.get('variant_id')
        if vid:
            parts.append(f'product #{pid} variant #{vid} × {qty}')
        else:
            parts.append(f'product #{pid} × {qty}')
    return '; '.join(parts[:8]) if parts else '—'


def _build_backfill_summary(validated_data: Dict[str, Any]) -> dict:
    occurred_at = validated_data.get('occurred_at')
    served_by_id = validated_data.get('served_by_id')
    served_label = '—'
    if served_by_id:
        user = User.objects.filter(pk=served_by_id, is_active=True).first()
        if user:
            served_label = user.get_full_name().strip() or user.username

    total_hint = validated_data.get('_preview_total')
    return {
        'occurred_at': occurred_at.isoformat() if occurred_at else '',
        'sale_type': validated_data.get('sale_type', 'pos'),
        'customer_id': validated_data.get('customer_id'),
        'payment_method': validated_data.get('payment_method', 'cash'),
        'amount_paid': str(validated_data.get('amount_paid', 0)),
        'served_by': served_label,
        'lines': _summarize_items(validated_data.get('items')),
        'total': str(total_hint) if total_hint is not None else '—',
    }


def _apply_payload_from_validated(validated_data: Dict[str, Any]) -> dict:
    return {k: _json_safe(v) for k, v in validated_data.items() if not k.startswith('_')}


def queue_sale_backfill(request, validated_data: Dict[str, Any]):
    if not sale_backfill_maker_checker_active():
        raise ValidationError('Maker-checker is not required for backfill.')

    occurred_at = validated_data.get('occurred_at')
    validate_backfill_occurred_at(occurred_at)
    reason = validate_backfill_reason(validated_data.get('backfill_reason', ''))

    items = validated_data.get('items') or []
    if not items:
        raise ValidationError({'items': 'At least one line item is required.'})

    staff = resolve_backfill_served_by(request.user, validated_data.get('served_by_id'))
    validated_data['served_by_id'] = staff.pk

    summary = _build_backfill_summary(validated_data)
    payload = _apply_payload_from_validated(validated_data)

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


def resubmit_sale_backfill(request, change: PendingChange, validated_data: Dict[str, Any]) -> PendingChange:
    """Send a rejected past-sale entry back to the checker queue after corrections."""
    if change.action_type != ACTION_SALE_BACKFILL:
        raise ValidationError('Only past sale entries can be resubmitted from here.')
    if change.status != PendingChange.STATUS_REJECTED:
        raise ValidationError('Only rejected submissions can be corrected and resubmitted.')
    if change.made_by_id != request.user.id:
        raise ValidationError('You can only resubmit your own past sale entries.')
    if not backfill_requires_approval():
        raise ValidationError('Maker-checker is not enabled for past sales.')

    occurred_at = validated_data.get('occurred_at')
    validate_backfill_occurred_at(occurred_at)
    reason = validate_backfill_reason(validated_data.get('backfill_reason', ''))

    items = validated_data.get('items') or []
    if not items:
        raise ValidationError({'items': 'At least one line item is required.'})

    staff = resolve_backfill_served_by(request.user, validated_data.get('served_by_id'))
    validated_data['served_by_id'] = staff.pk

    summary = _build_backfill_summary(validated_data)
    payload = _apply_payload_from_validated(validated_data)

    change.status = PendingChange.STATUS_PENDING
    change.reason = reason
    change.proposed_values = summary
    change.apply_payload = payload
    change.rejection_reason = ''
    change.checked_by = None
    change.checked_at = None
    change.save(
        update_fields=[
            'status',
            'reason',
            'proposed_values',
            'apply_payload',
            'rejection_reason',
            'checked_by',
            'checked_at',
        ]
    )
    from approvals.service import _audit_pending

    _audit_pending(request, change, 'pending_resubmit')
    return change
