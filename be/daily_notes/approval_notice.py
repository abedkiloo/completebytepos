"""Notify the requester in Daily notes when an approval is returned."""

from __future__ import annotations

import logging

from django.utils import timezone

from daily_notes.models import DailyNote, DailyTask

logger = logging.getLogger(__name__)

SOURCE_PENDING_CHANGE = 'pending_change'
SOURCE_EXPENSE = 'expense'
SOURCE_INCOME = 'income'
SOURCE_TRANSFER = 'transfer'

ACTION_LABELS = {
    'product_price': 'selling price change',
    'product_stock': 'stock change',
    'product_deactivate': 'product deactivation',
    'product_delete': 'product deletion',
    'product_unit': 'unit of measure change',
    'product_tax': 'tax rate change',
    'category_deactivate': 'category deactivation',
    'category_delete': 'category deletion',
    'stock_adjust': 'stock adjustment',
    'stock_purchase': 'stock purchase',
    'stock_transfer': 'stock transfer',
    'store_settings': 'store settings change',
    'payment_methods': 'payment methods change',
    'receipt_legal': 'receipt text change',
    'role_permissions': 'role permissions change',
    'sale_completed_edit': 'completed sale edit',
    'sale_refund': 'sale void / refund',
    'sale_rollback': 'sale rollback',
    'sale_backfill': 'past sale entry',
    'expense': 'expense',
    'income': 'income',
    'transfer': 'money transfer',
}


def action_label(action_type: str | None) -> str:
    key = str(action_type or '').strip()
    if not key:
        return 'request'
    return ACTION_LABELS.get(key, key.replace('_', ' '))


def _person_name(user) -> str:
    if user is None:
        return 'A reviewer'
    full = f'{getattr(user, "first_name", "")} {getattr(user, "last_name", "")}'.strip()
    return full or getattr(user, 'username', None) or 'A reviewer'


def build_rejection_notice(
    *,
    action_type: str,
    entity_repr: str,
    rejection_reason: str,
    checker,
    source: str,
    record_id,
) -> tuple[str, str]:
    label = action_label(action_type)
    item = (entity_repr or '').strip() or 'your request'
    checker_name = _person_name(checker)
    reason = (rejection_reason or '').strip() or 'No reason given'
    title = f'Approval rejected: {label}'[:200]
    content = (
        f'{checker_name} returned your {label} for {item}.\n'
        f'Reason: {reason}\n\n'
        'Nothing went live. Review the reason, fix the request if needed, '
        'then send it back for approval from Daily notes.\n'
        '---\n'
        f'source: {source}\n'
        f'id: {record_id}'
    )
    return title, content


def notify_approval_rejected(
    *,
    requester,
    checker,
    action_type: str,
    entity_repr: str = '',
    rejection_reason: str = '',
    source: str = SOURCE_PENDING_CHANGE,
    record_id=None,
):
    """Write a daily note and an open task for the person who requested approval."""
    if requester is None or record_id is None:
        return None
    today = timezone.localdate()
    title, content = build_rejection_notice(
        action_type=action_type,
        entity_repr=entity_repr,
        rejection_reason=rejection_reason,
        checker=checker,
        source=source,
        record_id=record_id,
    )
    try:
        note = DailyNote.objects.create(
            note_date=today,
            title=title,
            content=content,
            author=requester,
        )
        task = DailyTask.objects.create(
            task_date=today,
            title=title,
            description=content,
            author=checker or requester,
            assigned_to=requester,
        )
        return note, task
    except Exception:
        logger.exception('Could not write Daily notes rejection notice')
        return None
