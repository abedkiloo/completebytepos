"""
Employee claims for money they spent.

A normal employee files a claim. It appears in Expenses as a pending
claim. A manager approves or returns a staff claim. A director decides
a manager's own claim. The person who filed it cannot decide it.

Approving posts the row as an approved expense and tries the same
journal as a store expense. It does not change stock, wallets, or sales.

Public entry points:
    - ``file_claim`` — create one pending claim
    - ``decide_claim`` — approve or return it
    - ``may_decide_claim`` — whether this person may decide this claim
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from employees.leave import is_director, is_manager
from expenses.models import Expense, ExpenseCategory

logger = logging.getLogger(__name__)

CLAIM_BACK_DAYS = 30
AMOUNT_MIN = Decimal('0.01')
AMOUNT_MAX = Decimal('99999999.99')
DESCRIPTION_MAX = 500
NOTE_MAX = 300
REASON_MAX = 300
VENDOR_MAX = 200
RECEIPT_MAX = 100
PAYMENT_METHODS = {code for code, _label in Expense.PAYMENT_METHODS}


def file_claim(user, data, image=None, branch=None) -> Expense:
    """
    Record one pending claim for the signed-in employee.

    Args:
        user: Authenticated employee. Stored as ``created_by``. The client
            cannot name a different person.
        data: Mapping with ``amount`` (0.01–99999999.99, 2 decimal places),
            ``description`` (1–500 characters), optional ``expense_date``
            (``YYYY-MM-DD``, today back through 30 days; blank means today),
            optional ``payment_method`` (``cash``, ``mpesa``, ``bank``,
            ``card``, or ``other``; blank means cash), optional ``category``
            (active category id), optional ``notes`` (0–300 characters),
            optional ``vendor`` (0–200) and ``receipt_number`` (0–100).
        image: Optional uploaded receipt photo, or None. Empty files are
            ignored. Intake follows the expense photo limits (at most 5 MiB
            in, stored at most 1.5 MiB).
        branch: Branch to store, or None when the shop is not using branches.

    Returns:
        The pending ``Expense`` with ``is_claim`` True.

    Raises:
        ValidationError: Amount, date, description, category, or photo is
            outside the bounds above.

    Side effects:
        Inserts one expense row. Does not post a journal, send SMS, or
        change stock.
    """
    amount = _amount(data.get('amount'))
    description = _bounded_text(
        data.get('description'),
        field='description',
        label='what this was for',
        minimum=1,
        maximum=DESCRIPTION_MAX,
    )
    day = _claim_day(data.get('expense_date'))
    method = str(data.get('payment_method') or 'cash').strip().lower()[:20] or 'cash'
    if method not in PAYMENT_METHODS:
        raise ValidationError({
            'payment_method': 'Choose cash, mpesa, bank, card, or other.',
        })
    notes = _bounded_text(
        data.get('notes'), field='notes', label='notes', minimum=0, maximum=NOTE_MAX,
    )
    vendor = _bounded_text(
        data.get('vendor'), field='vendor', label='vendor', minimum=0, maximum=VENDOR_MAX,
    )
    receipt = _bounded_text(
        data.get('receipt_number'),
        field='receipt_number',
        label='receipt number',
        minimum=0,
        maximum=RECEIPT_MAX,
    )
    category = _category(data.get('category'))
    photo = _photo(image)
    expense = Expense(
        branch=branch,
        category=category,
        amount=amount,
        description=description,
        payment_method=method,
        status='pending',
        vendor=vendor,
        receipt_number=receipt,
        expense_date=day,
        created_by=user,
        notes=notes,
        is_claim=True,
    )
    if photo is not None:
        expense.image = photo
    expense.save()
    return expense


def may_decide_claim(actor, expense: Expense) -> bool:
    """
    Whether this person may approve or return the claim.

    Args:
        actor: Signed-in user.
        expense: Claim row, or any expense.

    Returns:
        bool. False for a missing user, a row that is not a claim, or the
        person who filed it. A manager decides a normal employee's claim.
        A director decides a manager's claim. No writes.
    """
    if actor is None or expense is None or not getattr(expense, 'is_claim', False):
        return False
    if not getattr(actor, 'is_authenticated', False):
        return False
    if actor.id == expense.created_by_id:
        return False
    claimant = expense.created_by
    if is_manager(claimant) or is_director(claimant):
        return is_director(actor)
    return is_manager(actor) or is_director(actor)


@transaction.atomic
def decide_claim(actor, expense: Expense, decision: str, reason: str = '') -> Expense:
    """
    Approve or return one pending claim.

    Args:
        actor: Manager or director who is not the claimant.
        expense: Pending claim.
        decision: ``approved`` or ``rejected``. Other values are refused.
        reason: Required when returning, 1–300 characters. Ignored when
            approving. Blank is refused on a return.

    Returns:
        The same expense, now ``approved`` or ``rejected``.

    Raises:
        PermissionDenied: This person cannot decide this claim.
        ValidationError: It is not a pending claim, the decision is not
            one of the two words, or the return reason is missing or longer
            than 300 characters.

    Side effects:
        Approval sets ``approved_by`` and tries an accounting journal.
        A journal failure is logged and does not undo the approval.
        A return appends the reason to notes and notifies the employee
        on their daily notes. No SMS and no stock change.
    """
    if not getattr(expense, 'is_claim', False):
        raise ValidationError('This is not an employee claim.')
    if expense.status != 'pending':
        raise ValidationError('Only a pending claim can be decided.')
    if not may_decide_claim(actor, expense):
        raise PermissionDenied('You cannot decide this claim.')
    choice = str(decision or '').strip().lower()[:20]
    if choice == 'approved':
        return _approve(expense, actor)
    if choice == 'rejected':
        return _reject(expense, actor, reason)
    raise ValidationError({'decision': 'Choose approved or rejected.'})


def _approve(expense: Expense, actor) -> Expense:
    """
    Post a pending claim as an approved expense.

    Args:
        expense: Pending claim already checked by ``decide_claim``.
        actor: Person stored on ``approved_by``.

    Returns:
        The approved expense.

    Side effects:
        Saves status and approver. Best-effort journal. Completes any
        earlier return notice for this expense.
    """
    expense.status = 'approved'
    expense.approved_by = actor
    expense.save(update_fields=['status', 'approved_by', 'updated_at'])
    from daily_notes.approval_notice import SOURCE_EXPENSE, complete_rejection_notices

    complete_rejection_notices(source=SOURCE_EXPENSE, record_id=expense.id)
    try:
        from accounting.services import create_expense_journal_entry
        create_expense_journal_entry(expense)
    except Exception:
        logger.exception('Could not post a journal for expense claim %s', expense.pk)
    return expense


def _reject(expense: Expense, actor, reason: str) -> Expense:
    """
    Return a pending claim to the employee.

    Args:
        expense: Pending claim.
        actor: Person who returned it. Their username is stored in notes.
        reason: 1–300 characters. A phone number must not be added here.

    Returns:
        The rejected expense.

    Raises:
        ValidationError: The reason is blank or longer than 300 characters.
    """
    text = str(reason or '').strip()
    if not text or len(text) > REASON_MAX:
        raise ValidationError({
            'rejection_reason': 'Say why you are returning this claim, in 1–300 characters.',
        })
    expense.status = 'rejected'
    username = (getattr(actor, 'username', None) or 'manager')[:80]
    note = f'[Rejected by {username}] {text}'
    expense.notes = f'{expense.notes}\n{note}'.strip() if expense.notes else note
    expense.save(update_fields=['status', 'notes', 'updated_at'])
    from daily_notes.approval_notice import SOURCE_EXPENSE, notify_approval_rejected

    notify_approval_rejected(
        requester=expense.created_by,
        checker=actor,
        action_type='expense',
        entity_repr=expense.expense_number or 'Expense claim',
        rejection_reason=text,
        source=SOURCE_EXPENSE,
        record_id=expense.id,
    )
    return expense


def _amount(raw) -> Decimal:
    """
    Parse a claim amount.

    Args:
        raw: Number or numeric string.

    Returns:
        Decimal with 2 places, from 0.01 through 99999999.99.

    Raises:
        ValidationError: Missing, not a number, or outside that range.
    """
    try:
        amount = Decimal(str(raw).strip()).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, AttributeError, ValueError):
        raise ValidationError({'amount': 'Enter an amount like 150.00.'})
    if amount < AMOUNT_MIN or amount > AMOUNT_MAX:
        raise ValidationError({'amount': 'Enter an amount from 0.01 to 99999999.99.'})
    return amount


def _claim_day(raw):
    """
    Parse the day the money was spent.

    Args:
        raw: ``YYYY-MM-DD``, or blank for today.

    Returns:
        datetime.date from 30 days ago through today, inclusive.

    Raises:
        ValidationError: The text is not a date or is outside that window.
    """
    text = str(raw or '').strip()[:10]
    today = timezone.localdate()
    if not text:
        return today
    try:
        day = datetime.strptime(text, '%Y-%m-%d').date()
    except ValueError:
        raise ValidationError({'expense_date': 'Use a date like 2026-11-23.'})
    start = today - timedelta(days=CLAIM_BACK_DAYS)
    if day < start or day > today:
        raise ValidationError({
            'expense_date': (
                f'A claim must be between {start.isoformat()} and {today.isoformat()}.'
            ),
        })
    return day


def _bounded_text(raw, *, field: str, label: str, minimum: int, maximum: int) -> str:
    """
    Strip a text field and keep it inside a length.

    Args:
        raw: Any value. None and non-strings become an empty string.
        field: Error key.
        label: Words used in the error.
        minimum: Inclusive lower length after strip. 0 allows blank.
        maximum: Inclusive upper length. 100–500 depending on the field.

    Returns:
        The stripped string.

    Raises:
        ValidationError: The length is outside ``minimum``–``maximum``.
    """
    text = str(raw or '').strip()
    if len(text) < minimum or len(text) > maximum:
        if minimum == 0:
            message = f'{label[:1].upper()}{label[1:]} can be at most {maximum} characters.'
        else:
            message = f'Say {label}, in {minimum}–{maximum} characters.'
        raise ValidationError({field: message})
    return text


def _category(raw):
    """
    Resolve an optional active category.

    Args:
        raw: Category id, or blank / None for no category.

    Returns:
        ExpenseCategory or None.

    Raises:
        ValidationError: The id is not a positive integer of an active category.
    """
    if raw in (None, '', 'null'):
        return None
    try:
        category_id = int(raw)
    except (TypeError, ValueError):
        raise ValidationError({'category': 'Choose a category.'})
    if category_id < 1:
        raise ValidationError({'category': 'Choose a category.'})
    category = ExpenseCategory.objects.filter(pk=category_id, is_active=True).first()
    if category is None:
        raise ValidationError({'category': 'That category is not available.'})
    return category


def _photo(image):
    """
    Compress an optional claim photo.

    Args:
        image: Uploaded file, or None / empty.

    Returns:
        Compressed file, or None when nothing was sent.

    Raises:
        ValidationError: The file is empty, over 5 MiB, or not an image.
    """
    if not image:
        return None
    from utils.image_upload import (
        GENERAL_MAX_INPUT_BYTES,
        TARGET_STORED_BYTES,
        prepare_uploaded_image,
    )

    return prepare_uploaded_image(
        image,
        field_name='image',
        max_input_bytes=GENERAL_MAX_INPUT_BYTES,
        target_bytes=TARGET_STORED_BYTES,
        label='Claim photo',
        preferred_name=getattr(image, 'name', 'claim.jpg') or 'claim.jpg',
    )
