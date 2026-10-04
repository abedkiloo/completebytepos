"""Notify the requester in Daily notes when an approval is returned."""

from __future__ import annotations

import logging
import re

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


def backfill_return_notice_fingerprint(change_id) -> str:
    return f'ref: reject/backfill/{change_id}/'


def rejection_notice_fingerprint(source: str, record_id) -> str:
    return f'ref: reject/{source}/{record_id}/'


PAST_SALE_TITLE = 'past sale entry'


def _id_pattern(prefix: str, record_id) -> re.Pattern:
    """``prefix`` + id, never followed by another digit (so 15 does not match 150)."""
    return re.compile(re.escape(f'{prefix}{record_id}') + r'(?!\d)')


def _matching(queryset, field: str, prefix: str, record_id) -> list:
    if record_id is None:
        return []
    pattern = _id_pattern(prefix, record_id)
    candidates = queryset.filter(**{f'{field}__contains': f'{prefix}{record_id}'})
    return [row for row in candidates if pattern.search(getattr(row, field) or '')]


_SALE_ID_LINE = re.compile(r'(?m)^sale_id:\s*\d+')

SALE_RETURN_TICK_ERROR = (
    'Open this sale, resolve the manager comment, then send it back for approval. '
    'Ticking this note is not enough.'
)


def is_sale_return_notice_text(text: str | None) -> bool:
    """True when the Daily note/task is a returned sale that must be fixed on POS."""
    raw = text or ''
    if 'ref: reject/sale/' in raw or 'ref: reject/backfill/' in raw:
        return True
    return bool(_SALE_ID_LINE.search(raw))


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
    elif action_type == 'sale_complete':
        footer += f'\n{sale_return_notice_fingerprint(record_id)}'
    elif action_type == 'sale_backfill':
        footer += f'\n{backfill_return_notice_fingerprint(record_id)}'
    footer += f'\n{rejection_notice_fingerprint(source, record_id)}'

    if action_type == 'sale_complete':
        number = item if item != 'your request' else 'this sale'
        customer = _sale_customer_label(sale)
        content = (
            f'{checker_name} returned sale {number} for {customer}.\n'
            f'Their comment:\n{reason}\n\n'
            'The sale is back on your POS cart. Open that sale, resolve the '
            'comment, then send it back for approval from POS. Ticking this '
            'note is not enough.\n'
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


def _complete_open_tasks(queryset) -> int:
    closed = 0
    now = timezone.now()
    for task in queryset:
        try:
            if task.is_done:
                continue
            task.mark_done(done=True, at=now)
            task.save(update_fields=['is_done', 'completed_at'])
            closed += 1
        except Exception:
            logger.exception('Could not complete Daily notes sale task')
    return closed


def _move_notes_to_past(notes) -> int:
    moved = 0
    for note in notes:
        try:
            if note.is_done:
                continue
            note.move_to_board('past')
            note.save(update_fields=['is_done', 'in_progress', 'completed_at', 'updated_at'])
            moved += 1
        except Exception:
            logger.exception('Could not move Daily notes card to Past')
    return moved


def _close_by_ref(prefix: str, record_id, *, title_filter=None) -> int:
    """Move matching open notes to Past and tick matching open tasks."""
    notes = DailyNote.objects.filter(is_done=False)
    tasks = DailyTask.objects.filter(is_done=False)
    if title_filter is not None:
        notes = title_filter(notes)
        tasks = title_filter(tasks)
    moved = _move_notes_to_past(_matching(notes, 'content', prefix, record_id))
    _complete_open_tasks(_matching(tasks, 'description', prefix, record_id))
    return moved


def _not_past_sale(qs):
    return qs.exclude(title__icontains=PAST_SALE_TITLE)


def _only_past_sale(qs):
    return qs.filter(title__icontains=PAST_SALE_TITLE)


def complete_sale_return_notes(*, record_id) -> int:
    """Move the salesperson's returned-sale sticky note and task to Past."""
    if record_id is None:
        return 0
    return _close_by_ref('ref: reject/sale/', record_id, title_filter=_not_past_sale)


def complete_backfill_return_notes(*, change_id) -> int:
    """Move a returned past-sale entry's sticky note and task to Past."""
    if change_id is None:
        return 0
    moved = _close_by_ref('ref: reject/backfill/', change_id)
    moved += _close_by_ref('ref: reject/sale/', change_id, title_filter=_only_past_sale)
    return moved


def complete_rejection_notices(*, source: str, record_id) -> int:
    """Clear the requester's "Approval rejected" note and task once it is resubmitted or approved."""
    if record_id is None:
        return 0
    moved = _close_by_ref(f'ref: reject/{source}/', record_id)
    moved += _close_by_ref(f'source: {source}\nid: ', record_id)
    return moved


def sale_approved_notice_fingerprint(record_id) -> str:
    return f'ref: approve/sale/{record_id}/'


_APPROVE_REF = re.compile(r'ref: approve/sale/(\d+)/')
_REJECT_REF = re.compile(r'ref: reject/sale/(\d+)/')
_APPROVED_TITLE = re.compile(r'^Sale #(.+?) was approved')

_POSTED_SALE_STATUSES = frozenset({'awaiting_payment', 'completed', 'cancelled'})


def build_sale_approved_notice(*, sale_number: str, checker, sale_id=None) -> tuple[str, str]:
    checker_name = _person_name(checker)
    number = (sale_number or '').strip() or 'this sale'
    title = f'Sale #{number} was approved'[:200]
    footer = ''
    if sale_id is not None:
        footer = f'\n---\n{sale_approved_notice_fingerprint(sale_id)}'
    content = (
        f'Sale #{number} was approved and completed. You can print the receipt.\n'
        f'Approved by {checker_name}.'
        f'{footer}'
    )
    return title, content


def complete_sale_approved_notices(*, sale) -> int:
    """Close leftover open tasks after a sale is approved or collected."""
    if sale is None:
        return 0
    record_id = getattr(sale, 'pk', None)
    closed = 0
    if record_id is not None:
        closed += complete_sale_return_notes(record_id=record_id)
        closed += _complete_open_tasks(
            _matching(
                DailyTask.objects.filter(is_done=False),
                'description',
                'ref: approve/sale/',
                record_id,
            )
        )
        closed += _complete_open_tasks(
            _matching(
                DailyTask.objects.filter(is_done=False),
                'description',
                f'ref: {SOURCE_SALE_COMPLETE}/',
                record_id,
            )
        )
    number = (getattr(sale, 'sale_number', None) or '').strip()
    if number:
        closed += _complete_open_tasks(
            DailyTask.objects.filter(
                title__startswith=f'Sale #{number} was approved',
                is_done=False,
            )
        )
    return closed


_REF_RULES = (
    (re.compile(r'ref: sale_complete/(\d+)'), 'sale_queue'),
    (re.compile(r'ref: sale_backfill/(\d+)'), 'backfill_queue'),
    (re.compile(r'ref: reject/backfill/(\d+)/'), 'backfill_return'),
    (_REJECT_REF, 'sale_return'),
    (_APPROVE_REF, 'sale_approved'),
    (re.compile(r'ref: reject/(pending_change|expense|income|transfer)/(\d+)/'), 'rejection'),
    (re.compile(r'(?m)^source: (pending_change|expense|income|transfer)\nid: (\d+)$'), 'rejection'),
)

_REJECTION_MODELS = {
    'expense': ('expenses', 'Expense', 'rejected'),
    'income': ('income', 'Income', 'rejected'),
    'transfer': ('transfers', 'MoneyTransfer', 'cancelled'),
}


def _sale_status(pk):
    from sales.models import Sale

    return Sale.objects.filter(pk=pk).values_list('status', flat=True).first()


def _change_status(pk):
    from approvals.models import PendingChange

    return PendingChange.objects.filter(pk=pk).values_list('status', flat=True).first()


def _still_rejected(source: str, pk) -> bool:
    if source == SOURCE_PENDING_CHANGE:
        from approvals.models import PendingChange

        return _change_status(pk) == PendingChange.STATUS_REJECTED
    app_label, model_name, rejected_status = _REJECTION_MODELS[source]
    from django.apps import apps

    model = apps.get_model(app_label, model_name)
    return model.objects.filter(pk=pk).values_list('status', flat=True).first() == rejected_status


def _notice_is_resolved(title: str, text: str) -> bool:
    """True when the record behind an approval card no longer needs anyone to act."""
    from approvals.models import PendingChange

    blob = f'{title or ""}\n{text or ""}'
    past_sale = PAST_SALE_TITLE in (title or '').lower()
    for pattern, kind in _REF_RULES:
        match = pattern.search(blob)
        if not match:
            continue
        if kind == 'sale_queue':
            return _sale_status(int(match.group(1))) != 'pending_approval'
        if kind == 'backfill_queue':
            return _change_status(int(match.group(1))) != PendingChange.STATUS_PENDING
        if kind == 'backfill_return' or (kind == 'sale_return' and past_sale):
            return _change_status(int(match.group(1))) != PendingChange.STATUS_REJECTED
        if kind == 'sale_return':
            return _sale_status(int(match.group(1))) != 'holding'
        if kind == 'sale_approved':
            return _sale_status(int(match.group(1))) in _POSTED_SALE_STATUSES
        if kind == 'rejection':
            return not _still_rejected(match.group(1), int(match.group(2)))
    titled = _APPROVED_TITLE.match((title or '').strip())
    if titled:
        number = titled.group(1).strip()
        if number and number != 'this sale':
            from sales.models import Sale

            status = Sale.objects.filter(sale_number=number).values_list('status', flat=True).first()
            return status in _POSTED_SALE_STATUSES
    return False


def _notice_filter(text_field: str):
    from django.db.models import Q

    return (
        Q(**{f'{text_field}__contains': 'ref: '})
        | Q(**{f'{text_field}__contains': 'source: '})
        | Q(title__startswith='Sale #')
    )


def complete_stale_approval_notices(*, user=None) -> int:
    """Close open approval notes and tasks whose sale or request has already been dealt with."""
    from django.db.models import Q

    notes = DailyNote.objects.filter(is_done=False).filter(_notice_filter('content'))
    tasks = DailyTask.objects.filter(is_done=False).filter(_notice_filter('description'))
    if user is not None:
        notes = notes.filter(Q(assigned_to=user) | Q(author=user))
        tasks = tasks.filter(Q(assigned_to=user) | Q(author=user))
    closed = 0
    for note in notes:
        try:
            if _notice_is_resolved(note.title, note.content):
                closed += _move_notes_to_past([note])
        except Exception:
            logger.exception('Could not check Daily notes approval card %s', note.pk)
    for task in tasks:
        try:
            if _notice_is_resolved(task.title, task.description):
                closed += _complete_open_tasks([task])
        except Exception:
            logger.exception('Could not check Daily notes approval task %s', task.pk)
    return closed


def complete_stale_sale_notice_tasks(*, user=None) -> int:
    return complete_stale_approval_notices(user=user)


def notify_sale_approved(*, sale, checker):
    """Tell the cashier in Daily notes that the sale is complete."""
    requester = getattr(sale, 'cashier', None)
    if requester is None:
        return None
    complete_sale_approved_notices(sale=sale)
    today = timezone.localdate()
    title, content = build_sale_approved_notice(
        sale_number=getattr(sale, 'sale_number', '') or str(getattr(sale, 'pk', '')),
        checker=checker,
        sale_id=getattr(sale, 'pk', None),
    )
    try:
        note = DailyNote.objects.create(
            note_date=today,
            title=title,
            content=content,
            author=requester,
            is_done=True,
            completed_at=timezone.now(),
        )
        return note
    except Exception:
        logger.exception('Could not write Daily notes sale-approved notice')
        return None


SOURCE_SALE_COMPLETE = 'sale_complete'
SOURCE_SALE_BACKFILL = 'sale_backfill'


def sale_queue_notice_fingerprint(source: str, record_id) -> str:
    return f'ref: {source}/{record_id}/'


def _notes_for_sale_queue(source: str, record_id) -> list:
    return _matching(DailyNote.objects.all(), 'content', f'ref: {source}/', record_id)


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
    return _close_by_ref(f'ref: {source}/', record_id)


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


def complete_requester_notices_for_change(change) -> int:
    """Clear the requester's rejection note once the change is resubmitted or approved."""
    change_id = getattr(change, 'id', None)
    moved = complete_rejection_notices(source=SOURCE_PENDING_CHANGE, record_id=change_id)
    if getattr(change, 'action_type', '') == 'sale_backfill':
        moved += complete_backfill_return_notes(change_id=change_id)
    return moved


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
