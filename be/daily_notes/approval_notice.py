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
    'sale_complete': 'sale completion',
    'sale_backfill': 'past sale entry',
    'debt_collection': 'debt collection',
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


SALE_RETURN_ACTIONS = frozenset({'sale_complete', 'sale_backfill'})


def sale_return_notice_fingerprint(record_id) -> str:
    return f'ref: reject/sale/{record_id}/'


def _sale_customer_label(sale) -> str:
    if sale is None:
        return 'the customer'
    name = (getattr(sale, 'customer_name', None) or '').strip()
    if not name:
        customer = getattr(sale, 'customer', None)
        name = (getattr(customer, 'name', None) or '').strip() if customer else ''
    return name or 'walk-in customer'


def build_rejection_notice(
    *,
    action_type: str,
    entity_repr: str,
    rejection_reason: str,
    checker,
    source: str,
    record_id,
    sale=None,
) -> tuple[str, str]:
    label = action_label(action_type)
    item = (entity_repr or '').strip() or 'your request'
    checker_name = _person_name(checker)
    reason = (rejection_reason or '').strip() or 'No reason given'
    title = f'Approval rejected: {label}'[:200]
    footer = f'source: {source}\nid: {record_id}'
    sale_pk = getattr(sale, 'pk', None)
    if action_type == 'sale_complete' and sale_pk is not None:
        footer += f'\nsale_id: {sale_pk}\n{sale_return_notice_fingerprint(sale_pk)}'
    elif action_type in SALE_RETURN_ACTIONS:
        footer += f'\n{sale_return_notice_fingerprint(sale_pk or record_id)}'

    if action_type == 'sale_complete':
        number = item if item != 'your request' else 'this sale'
        customer = _sale_customer_label(sale)
        content = (
            f'{checker_name} returned sale {number} for {customer}.\n'
            f'Their comment:\n{reason}\n\n'
            'The sale is back on your POS cart. Fix it, then send it back '
            'for approval from Daily notes or POS.\n'
            '---\n'
            f'{footer}'
        )
    else:
        content = (
            f'{checker_name} returned your {label} for {item}.\n'
            f'Reason: {reason}\n\n'
            'Nothing went live. Review the reason, fix the request if needed, '
            'then send it back for approval from Daily notes.\n'
            '---\n'
            f'{footer}'
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
    is_sticky: bool = False,
    sale=None,
):
    """Write a daily note and an open task for the person who requested approval."""
    if requester is None or record_id is None:
        return None
    sticky = bool(is_sticky) or action_type in SALE_RETURN_ACTIONS
    today = timezone.localdate()
    title, content = build_rejection_notice(
        action_type=action_type,
        entity_repr=entity_repr,
        rejection_reason=rejection_reason,
        checker=checker,
        source=source,
        record_id=record_id,
        sale=sale,
    )
    try:
        note = DailyNote.objects.create(
            note_date=today,
            title=title,
            content=content,
            author=(checker or requester) if sticky else requester,
            assigned_to=requester if sticky else None,
            is_sticky=sticky,
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


def complete_sale_return_notes(*, record_id) -> int:
    """Move the salesperson's returned-sale sticky note and task to Past."""
    if record_id is None:
        return 0
    fingerprint = sale_return_notice_fingerprint(record_id)
    moved = 0
    now = timezone.now()
    for note in DailyNote.objects.filter(content__contains=fingerprint, is_done=False):
        try:
            note.move_to_board('past')
            note.save(update_fields=['is_done', 'in_progress', 'completed_at', 'updated_at'])
            moved += 1
        except Exception:
            logger.exception('Could not complete Daily notes sale-return card')
    for task in DailyTask.objects.filter(description__contains=fingerprint, is_done=False):
        try:
            task.mark_done(done=True, at=now)
            task.save(update_fields=['is_done', 'completed_at'])
        except Exception:
            logger.exception('Could not complete Daily notes sale-return task')
    return moved


def build_sale_approved_notice(*, sale_number: str, checker) -> tuple[str, str]:
    checker_name = _person_name(checker)
    number = (sale_number or '').strip() or 'this sale'
    title = f'Sale #{number} was approved'[:200]
    content = (
        f'Sale #{number} was approved. You can issue the receipt now.\n'
        f'Approved by {checker_name}.'
    )
    return title, content


def notify_sale_approved(*, sale, checker):
    """Tell the cashier in Daily notes that they can print the receipt."""
    requester = getattr(sale, 'cashier', None)
    if requester is None:
        return None
    today = timezone.localdate()
    title, content = build_sale_approved_notice(
        sale_number=getattr(sale, 'sale_number', '') or str(getattr(sale, 'pk', '')),
        checker=checker,
    )
    try:
        note = DailyNote.objects.create(
            note_date=today,
            title=title,
            content=content,
            author=requester,
        )
        DailyTask.objects.create(
            task_date=today,
            title=title,
            description=content,
            author=checker or requester,
            assigned_to=requester,
        )
        return note
    except Exception:
        logger.exception('Could not write Daily notes sale-approved notice')
        return None


SOURCE_SALE_COMPLETE = 'sale_complete'
SOURCE_SALE_BACKFILL = 'sale_backfill'


def sale_queue_notice_fingerprint(source: str, record_id) -> str:
    return f'ref: {source}/{record_id}'


def _notes_for_sale_queue(source: str, record_id):
    if record_id is None:
        return DailyNote.objects.none()
    return DailyNote.objects.filter(
        content__contains=sale_queue_notice_fingerprint(source, record_id)
    )


def manager_notice_recipients(*, exclude_user=None):
    """Managers (then sales.approve staff) who should clear a queued sale."""
    from django.contrib.auth.models import User

    from accounts.models import Permission, Role
    from accounts.role_definitions import ROLE_MANAGER
    from daily_notes.services import users_with_role

    seen = {}
    role = Role.objects.filter(name=ROLE_MANAGER).first()
    for user in users_with_role(role):
        seen[user.pk] = user
    for user in User.objects.filter(is_active=True, profile__role='manager'):
        seen[user.pk] = user

    if not seen:
        perm = Permission.objects.filter(module='sales', action='approve').first()
        if perm is not None:
            for user in User.objects.filter(
                is_active=True,
                profile__custom_role__permissions=perm,
            ).distinct():
                seen[user.pk] = user

    exclude_id = getattr(exclude_user, 'pk', None)
    return [user for user in seen.values() if user.pk != exclude_id]


def build_manager_sale_queue_notice(
    *,
    author,
    source: str,
    record_id,
    sale=None,
    entity_repr: str = '',
) -> tuple[str, str]:
    agent = _person_name(author)
    fingerprint = sale_queue_notice_fingerprint(source, record_id)
    if source == SOURCE_SALE_BACKFILL:
        item = (entity_repr or '').strip() or 'a past sale'
        title = f'Clear and move: {item}'[:200]
        lead = f'{agent} added {item}.'
    else:
        number = (
            getattr(sale, 'sale_number', None)
            or (entity_repr or '').strip()
            or str(record_id)
        )
        total = getattr(sale, 'total', None)
        amount = f' (KES {total})' if total is not None else ''
        title = f'Clear and move: {number}'[:200]
        lead = f'{agent} added sale {number}{amount}.'
    content = (
        f'{lead}\n'
        'Approve it on Approve sales so stock and books can move.\n'
        'This card stays in To do until you approve or reject. Then it moves to Past.\n'
        '---\n'
        f'{fingerprint}'
    )
    return title, content


def notify_managers_sale_queued(
    *,
    author,
    source: str,
    record_id,
    sale=None,
    entity_repr: str = '',
):
    """Put a To do card on each manager Daily notes board for a queued sale."""
    if author is None or record_id is None:
        return []
    existing = list(_notes_for_sale_queue(source, record_id))
    open_notes = [note for note in existing if not note.is_done]
    if open_notes:
        return open_notes
    if existing:
        reopened = []
        for note in existing:
            try:
                note.move_to_board('todo')
                note.save(update_fields=['is_done', 'in_progress', 'completed_at', 'updated_at'])
                reopened.append(note)
            except Exception:
                logger.exception('Could not reopen Daily notes sale-queue card')
        return reopened

    recipients = manager_notice_recipients(exclude_user=author)
    if not recipients:
        return []

    today = timezone.localdate()
    title, content = build_manager_sale_queue_notice(
        author=author,
        source=source,
        record_id=record_id,
        sale=sale,
        entity_repr=entity_repr,
    )
    try:
        from daily_notes.services import create_notes_for_assignees

        notes = []
        for manager in recipients:
            notes.extend(
                create_notes_for_assignees(
                    author=manager,
                    note_date=today,
                    title=title,
                    content=content,
                    assigned_to=manager,
                )
            )
        return notes
    except Exception:
        logger.exception('Could not write Daily notes manager sale-queue cards')
        return []


def complete_manager_queue_notes(*, source: str, record_id) -> int:
    """Move the manager sale-queue cards to Past (done)."""
    if record_id is None:
        return 0
    moved = 0
    for note in _notes_for_sale_queue(source, record_id).filter(is_done=False):
        try:
            note.move_to_board('past')
            note.save(update_fields=['is_done', 'in_progress', 'completed_at', 'updated_at'])
            moved += 1
        except Exception:
            logger.exception('Could not move Daily notes sale-queue card to Past')
    return moved


def complete_manager_notes_for_change(change) -> int:
    action = getattr(change, 'action_type', '')
    if action == SOURCE_SALE_COMPLETE or action == 'sale_complete':
        return complete_manager_queue_notes(
            source=SOURCE_SALE_COMPLETE,
            record_id=getattr(change, 'entity_id', None),
        )
    if action == SOURCE_SALE_BACKFILL or action == 'sale_backfill':
        return complete_manager_queue_notes(
            source=SOURCE_SALE_BACKFILL,
            record_id=getattr(change, 'id', None),
        )
    return 0


def notify_managers_for_change(*, author, change, sale=None):
    action = getattr(change, 'action_type', '')
    if action == 'sale_complete':
        record_id = getattr(sale, 'pk', None) or getattr(change, 'entity_id', None)
        return notify_managers_sale_queued(
            author=author,
            source=SOURCE_SALE_COMPLETE,
            record_id=record_id,
            sale=sale,
            entity_repr=getattr(change, 'entity_repr', '') or '',
        )
    if action == 'sale_backfill':
        return notify_managers_sale_queued(
            author=author,
            source=SOURCE_SALE_BACKFILL,
            record_id=getattr(change, 'id', None),
            entity_repr=getattr(change, 'entity_repr', '') or '',
        )
    return []
