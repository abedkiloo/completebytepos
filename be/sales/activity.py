"""Accountability timeline for a single sale — who did what, and when."""

from __future__ import annotations

from typing import Any

from django.utils.dateparse import parse_datetime

from approvals.models import PendingChange
from approvals.registry import (
    ACTION_SALE_BACKFILL,
    ACTION_SALE_COMPLETE,
    ACTION_SALE_REFUND,
    ACTION_SALE_ROLLBACK,
)

SALE_ACTION_TYPES = (
    ACTION_SALE_COMPLETE,
    ACTION_SALE_REFUND,
    ACTION_SALE_ROLLBACK,
    ACTION_SALE_BACKFILL,
)

_ACTION_LABELS = {
    ACTION_SALE_COMPLETE: {
        'submitted': 'Submitted for approval',
        'approved': 'Sale approved',
        'rejected': 'Sale returned for correction',
        'pending': 'Awaiting approval',
    },
    ACTION_SALE_REFUND: {
        'submitted': 'Void / refund requested',
        'approved': 'Void / refund approved',
        'rejected': 'Void / refund rejected',
        'pending': 'Void / refund awaiting approval',
    },
    ACTION_SALE_ROLLBACK: {
        'submitted': 'Rollback requested',
        'approved': 'Rollback approved',
        'rejected': 'Rollback rejected',
        'pending': 'Rollback awaiting approval',
    },
    ACTION_SALE_BACKFILL: {
        'submitted': 'Past sale submitted',
        'approved': 'Past sale approved',
        'rejected': 'Past sale rejected',
        'pending': 'Past sale awaiting approval',
    },
}


def _username(user) -> str | None:
    if not user:
        return None
    full = (user.get_full_name() or '').strip()
    return full or user.username


def _iso(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def _event(
    *,
    event_id: str,
    kind: str,
    label: str,
    at,
    actor: str | None = None,
    actor_role: str | None = None,
    comment: str = '',
    detail: str = '',
) -> dict[str, Any]:
    return {
        'id': event_id,
        'kind': kind,
        'label': label,
        'at': _iso(at),
        'actor': actor or None,
        'actor_role': actor_role or None,
        'comment': (comment or '').strip(),
        'detail': (detail or '').strip(),
    }


def _sort_key(event: dict[str, Any]):
    raw = event.get('at') or ''
    parsed = parse_datetime(raw) if isinstance(raw, str) else None
    # Stable secondary key so recorded stays first when timestamps match.
    order_hint = 0 if event.get('kind') == 'recorded' else 1
    return (parsed.timestamp() if parsed else 0.0, order_hint, event.get('id') or '')


def build_sale_activity(sale) -> list[dict[str, Any]]:
    """
    Build a chronological accountability trail for ``sale``.

    Sources: sale actors, PendingChange rows, SaleRefund rows, and key audit events.
    """
    events: list[dict[str, Any]] = []

    cashier = _username(getattr(sale, 'cashier', None))
    events.append(
        _event(
            event_id=f'recorded-{sale.pk}',
            kind='recorded',
            label='Sale recorded',
            at=getattr(sale, 'created_at', None) or getattr(sale, 'occurred_at', None),
            actor=cashier,
            actor_role='Cashier',
            detail=(
                f'Sale date {sale.occurred_at.isoformat()}'
                if getattr(sale, 'occurred_at', None)
                else ''
            ),
            comment=(getattr(sale, 'backfill_reason', None) or '')
            if getattr(sale, 'entry_source', '') == 'backfill'
            else '',
        )
    )

    served = getattr(sale, 'served_by', None)
    if served and getattr(sale, 'cashier_id', None) and served.pk != sale.cashier_id:
        events.append(
            _event(
                event_id=f'served-{sale.pk}',
                kind='served_by',
                label='Attributed to salesperson',
                at=getattr(sale, 'created_at', None),
                actor=_username(served),
                actor_role='Salesperson',
            )
        )

    changes = (
        PendingChange.objects.filter(
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            action_type__in=SALE_ACTION_TYPES,
        )
        .select_related('made_by', 'checked_by')
        .order_by('made_at', 'id')
    )
    for change in changes:
        labels = _ACTION_LABELS.get(change.action_type, {})
        maker = _username(change.made_by)
        if change.status == PendingChange.STATUS_PENDING:
            events.append(
                _event(
                    event_id=f'change-pending-{change.pk}',
                    kind='pending',
                    label=labels.get('pending') or labels.get('submitted') or 'Awaiting approval',
                    at=change.made_at,
                    actor=maker,
                    actor_role='Requester',
                    comment=change.reason or '',
                )
            )
        else:
            events.append(
                _event(
                    event_id=f'change-submitted-{change.pk}',
                    kind='submitted',
                    label=labels.get('submitted') or 'Submitted for approval',
                    at=change.made_at,
                    actor=maker,
                    actor_role='Requester',
                    comment=change.reason or '',
                )
            )
            if change.status == PendingChange.STATUS_APPROVED:
                events.append(
                    _event(
                        event_id=f'change-approved-{change.pk}',
                        kind='approved',
                        label=labels.get('approved') or 'Approved',
                        at=change.checked_at or change.made_at,
                        actor=_username(change.checked_by),
                        actor_role='Approver',
                    )
                )
            elif change.status == PendingChange.STATUS_REJECTED:
                events.append(
                    _event(
                        event_id=f'change-rejected-{change.pk}',
                        kind='rejected',
                        label=labels.get('rejected') or 'Rejected',
                        at=change.checked_at or change.made_at,
                        actor=_username(change.checked_by),
                        actor_role='Approver',
                        comment=change.rejection_reason or '',
                    )
                )

    # Applied voids/rollbacks (covers admin immediate apply and post-approval apply).
    refunds = (
        sale.refunds.select_related('refunded_by').order_by('created_at', 'id')
        if hasattr(sale, 'refunds')
        else []
    )
    for refund in refunds:
        is_rollback = getattr(refund, 'refund_type', '') == 'rollback'
        events.append(
            _event(
                event_id=f'refund-{refund.pk}',
                kind='rollback' if is_rollback else 'void',
                label='Sale rolled back' if is_rollback else 'Void / refund applied',
                at=refund.created_at,
                actor=_username(refund.refunded_by),
                actor_role='Applied by',
                comment=(refund.reason or '').replace('[ROLLBACK] ', '').strip(),
                detail=(
                    f'{refund.refund_number} · {refund.amount}'
                    if getattr(refund, 'refund_number', None)
                    else str(getattr(refund, 'amount', '') or '')
                ),
            )
        )

    if getattr(sale, 'status', None) == 'cancelled':
        cancel_actor = None
        cancel_at = getattr(sale, 'updated_at', None)
        try:
            from accounts.models import AuditLog

            log = (
                AuditLog.objects.filter(
                    module='sales',
                    action='holding_cancel',
                    object_type='sales.Sale',
                    object_id=str(sale.pk),
                )
                .select_related('user')
                .order_by('-created_at')
                .first()
            )
            if log:
                cancel_actor = log.username_snapshot or _username(log.user)
                cancel_at = log.created_at
        except Exception:
            pass
        events.append(
            _event(
                event_id=f'cancelled-{sale.pk}',
                kind='cancelled',
                label='Sale cancelled',
                at=cancel_at,
                actor=cancel_actor,
                actor_role='Cancelled by',
            )
        )

    # Date corrections from audit (may be multiple).
    try:
        from accounts.models import AuditLog

        for log in (
            AuditLog.objects.filter(
                module='sales',
                action='update',
                object_type='sales.Sale',
                object_id=str(sale.pk),
            )
            .select_related('user')
            .order_by('created_at')
        ):
            changes = log.changes or {}
            if 'occurred_at_to' not in changes and 'occurred_at_from' not in changes:
                continue
            events.append(
                _event(
                    event_id=f'date-{log.pk}',
                    kind='date_corrected',
                    label='Sale date corrected',
                    at=log.created_at,
                    actor=log.username_snapshot or _username(log.user),
                    actor_role='Corrected by',
                    detail=(
                        f"{changes.get('occurred_at_from') or '—'} → "
                        f"{changes.get('occurred_at_to') or '—'}"
                    ),
                )
            )
    except Exception:
        pass

    events.sort(key=_sort_key)
    return events
