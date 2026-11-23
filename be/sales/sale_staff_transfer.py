"""
Move one completed sale from one salesperson to another.

An admin does this. The customer, the prices, the quantities, the
payments, and the stock stay. Commission and sales-by-person reports
follow the new person because they read ``served_by``, then ``cashier``.

A locked payslip for that month is not rewritten. The move is refused
until that pay is unlocked.

Public entry points:
    - ``user_may_move_sale_staff`` — admin gate
    - ``transfer_sale_staff`` — perform the move
    - ``staff_choices`` — names an admin can pick
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from approvals.permissions import user_has_admin_checker_override
from sales.models import Sale

ADMIN_ROLE_NAMES = frozenset({'Super Admin', 'Admin', 'Administrator'})
REASON_MAX = 200
NAME_MAX = 80
SEARCH_MAX = 80
CHOICE_MAX = 20
NOTE_MAX = 4000


def user_may_move_sale_staff(user) -> bool:
    """
    Whether this person may move a sale to another salesperson.

    Args:
        user: Signed-in user, or None.

    Returns:
        bool. True for a superuser, an admin, or a Super Admin role.
        A manager and a salesperson are false. No writes.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if user_has_admin_checker_override(user):
        return True
    profile = getattr(user, 'profile', None)
    role = getattr(profile, 'custom_role', None)
    return (getattr(role, 'name', None) or '').strip() in ADMIN_ROLE_NAMES


def staff_choices(query: str = '') -> list[dict]:
    """
    Active staff an admin can move a sale to.

    Args:
        query: Name or username, 0–80 characters. Blank returns the first
            20 active people. One or more characters narrows the list.

    Returns:
        Up to 20 dicts with ``id`` and ``display_name``. No phone, email,
        or pay. No writes.
    """
    term = str(query or '').strip()[:SEARCH_MAX]
    people = User.objects.filter(is_active=True, profile__is_active=True)
    if term:
        people = people.filter(
            Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(username__icontains=term)
        )
    rows = []
    for person in people.order_by('first_name', 'last_name', 'username')[:CHOICE_MAX]:
        rows.append({'id': person.id, 'display_name': _staff_name(person)})
    return rows


@transaction.atomic
def transfer_sale_staff(sale_id: int, target_user_id: int, user, reason: str = '') -> dict:
    """
    Credit one completed sale to another salesperson.

    Args:
        sale_id: Completed sale id, 1–2^31-1.
        target_user_id: Active staff user id, 1–2^31-1. Must not already
            be the only person on the sale.
        user: Admin performing the move.
        reason: Optional note, 0–200 characters. Blank is kept blank.

    Returns:
        Dict with the sale and the old and new staff users.

    Raises:
        PermissionDenied: The actor is not an admin.
        ValidationError: The sale is missing or not completed, the person
            is missing or inactive, the sale is already theirs, the reason
            is longer than 200 characters, or that month's pay is locked.

    Side effects:
        Sets ``cashier`` and ``served_by`` to the new person and appends
        a name-only note. Does not change the customer, money, stock,
        payments, or a locked payslip.
    """
    if not user_may_move_sale_staff(user):
        raise PermissionDenied('Only an admin can move a sale to another salesperson.')
    note = str(reason or '').strip()
    if len(note) > REASON_MAX:
        raise ValidationError({'reason': 'The note can be at most 200 characters.'})
    try:
        sale = Sale.objects.select_for_update().get(pk=int(sale_id))
    except (Sale.DoesNotExist, TypeError, ValueError):
        raise ValidationError('That sale was not found.')
    if sale.status != 'completed':
        raise ValidationError('Only a completed sale can move to another salesperson.')
    try:
        target_id = int(target_user_id)
    except (TypeError, ValueError):
        raise ValidationError({'user_id': 'Choose a salesperson.'})
    if target_id < 1:
        raise ValidationError({'user_id': 'Choose a salesperson.'})
    target = User.objects.filter(
        pk=target_id, is_active=True, profile__is_active=True,
    ).select_related('profile').first()
    if target is None:
        raise ValidationError({'user_id': 'Choose an active salesperson.'})
    if sale.cashier_id == target.id and sale.served_by_id in (None, target.id):
        raise ValidationError('This sale is already with that salesperson.')
    if _month_pay_is_locked(sale, target.id):
        raise ValidationError(
            'That month’s pay is already locked. Unlock it before moving this sale.'
        )
    previous = sale.served_by or sale.cashier
    sale.cashier = target
    sale.served_by = target
    sale.notes = _append_note(sale.notes, previous, target, note)
    sale.save(update_fields=['cashier', 'served_by', 'notes', 'updated_at'])
    return {'sale': sale, 'from_staff': previous, 'to_staff': target}


def _month_pay_is_locked(sale: Sale, target_user_id: int) -> bool:
    """
    Whether a locked payslip already covers this sale's month.

    Args:
        sale: Sale being moved. Uses ``occurred_at``, then ``created_at``.
        target_user_id: The salesperson who would receive the sale.

    Returns:
        True when the old or new person has a locked payslip in that
        calendar month. False when neither has one. No writes.
    """
    from employees.models import Employee
    from payroll.models import PayrollRun

    moment = sale.occurred_at or sale.created_at
    if moment is None:
        return False
    if timezone.is_aware(moment):
        moment = timezone.localtime(moment)
    user_ids = [target_user_id]
    if sale.cashier_id:
        user_ids.append(sale.cashier_id)
    if sale.served_by_id:
        user_ids.append(sale.served_by_id)
    employee_ids = list(
        Employee.objects.filter(user_id__in=user_ids).values_list('id', flat=True)
    )
    if not employee_ids:
        return False
    return PayrollRun.objects.filter(
        status=PayrollRun.STATUS_LOCKED,
        year=moment.year,
        month=moment.month,
        payslips__employee_id__in=employee_ids,
    ).exists()


def _append_note(existing: str, previous, target, reason: str) -> str:
    """
    Add a name-only line to the sale notes.

    Args:
        existing: Current notes, possibly blank.
        previous: Previous salesperson, or None.
        target: New salesperson.
        reason: Optional admin note, already trimmed to 200 characters.

    Returns:
        Notes of at most 4000 characters. The new line is kept.
    """
    line = f"Salesperson moved from {_staff_name(previous)} to {_staff_name(target)}"
    if reason:
        line = f'{line}. Reason: {reason}'
    text = f'{existing}\n{line}'.strip() if existing else line
    if len(text) <= NOTE_MAX:
        return text
    return text[-NOTE_MAX:]


def _staff_name(user) -> str:
    """
    Short display name, 1–80 characters.

    Args:
        user: Django user, or None.

    Returns:
        Full name, otherwise username, otherwise ``Staff``. No phone.
    """
    full = ''
    if user is not None:
        full = (user.get_full_name() or '').strip() or user.get_username()
    return (full or 'Staff')[:NAME_MAX]
