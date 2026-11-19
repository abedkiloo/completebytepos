"""
One-day leave and sick-day requests.

A sales person or any other employee asks a manager. A manager asks a
director. The decision is texted to the person who asked and to the
directors. A person cannot decide their own day.

Public entry points:
    - ``file_leave`` — create one pending day
    - ``decide_leave`` — approve or reject
    - ``leave_rows`` — the list the signed-in person may see
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from employees.models import LeaveRequest

logger = logging.getLogger(__name__)

NOTE_MAX = 300
LIST_MAX = 100
PEOPLE_MAX = 200
LEAVE_DAY_MAX = 31
SMS_MAX = 30
LEAVE_AHEAD_DAYS = 90
SICK_BACK_DAYS = 2
SICK_AHEAD_DAYS = 30
ROLE_DIRECTOR = 'Director'
ROLE_MANAGER = 'Manager'


def _profile(user):
    """
    Return the user's profile, or None.

    Args:
        user: Django user or None.

    Returns:
        UserProfile or None. No writes.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    return getattr(user, 'profile', None)


def is_director(user) -> bool:
    """
    True when this person decides a manager's day off.

    Args:
        user: Signed-in user.

    Returns:
        bool. Super Admin counts, as does legacy role ``director`` or
        job role Director. No writes.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    profile = _profile(user)
    if profile is None:
        return False
    if profile.role == 'director':
        return True
    role = getattr(profile, 'custom_role', None)
    return bool(role and role.name == ROLE_DIRECTOR)


def is_manager(user) -> bool:
    """
    True when this person is a manager and not a director.

    Args:
        user: Signed-in user.

    Returns:
        bool. No writes.
    """
    if is_director(user):
        return False
    profile = _profile(user)
    if profile is None:
        return False
    if profile.role == 'manager':
        return True
    role = getattr(profile, 'custom_role', None)
    return bool(role and role.name == ROLE_MANAGER)


def _name(user) -> str:
    """
    Short display name, 1–80 characters.

    Args:
        user: Django user.

    Returns:
        str. Never a phone number. No writes.
    """
    full = ''
    if user is not None:
        full = (user.get_full_name() or '').strip() or user.get_username()
    return (full or 'Staff')[:80]


def _today():
    """
    Today's date in the store timezone.

    Returns:
        datetime.date. No writes.
    """
    return timezone.localdate()


def _check_day(kind: str, day) -> None:
    """
    Keep a request inside the allowed window.

    Args:
        kind: ``leave`` or ``sick``.
        day: datetime.date.

    Returns:
        None.

    Raises:
        ValidationError: The day is outside the window.
    """
    today = _today()
    if kind == LeaveRequest.KIND_SICK:
        start = today - timedelta(days=SICK_BACK_DAYS)
        end = today + timedelta(days=SICK_AHEAD_DAYS)
        label = 'A sick day'
    else:
        start = today
        end = today + timedelta(days=LEAVE_AHEAD_DAYS)
        label = 'A day off'
    if day < start or day > end:
        raise ValidationError({
            'day': f'{label} must be between {start.isoformat()} and {end.isoformat()}.',
        })


def may_decide(actor, leave: LeaveRequest) -> bool:
    """
    Whether this person may approve or reject the request.

    Args:
        actor: Signed-in user.
        leave: Pending or closed request.

    Returns:
        bool. The requester is never allowed. A manager decides staff.
        A director decides a manager. No writes.
    """
    if actor is None or leave is None:
        return False
    if actor.id == leave.user_id:
        return False
    if is_manager(leave.user) or is_director(leave.user):
        return is_director(actor)
    return is_manager(actor) or is_director(actor)


def leave_rows(user) -> list:
    """
    Requests this person may see.

    Args:
        user: Signed-in user.

    Returns:
        list[LeaveRequest]: Their own rows, plus pending rows they may
        decide. At most 100. No writes.
    """
    own = LeaveRequest.objects.filter(user=user)
    pending = LeaveRequest.objects.filter(status=LeaveRequest.STATUS_PENDING).exclude(user=user)
    visible_ids = set(own.values_list('id', flat=True)[:LIST_MAX])
    for row in pending.select_related('user', 'user__profile', 'user__profile__custom_role')[:LIST_MAX]:
        if may_decide(user, row):
            visible_ids.add(row.id)
    return list(
        LeaveRequest.objects.filter(id__in=visible_ids)
        .select_related('user', 'decided_by')
        .order_by('status', '-day')[:LIST_MAX]
    )


def file_leave(user, *, kind: str, day, note: str = '') -> LeaveRequest:
    """
    Ask for one day off or one sick day.

    Args:
        user: The employee. They become the requester.
        kind: ``leave`` or ``sick``.
        day: datetime.date. Leave is today through 90 days. Sick is
            2 days back through 30 days ahead.
        note: Optional reason, 0–300 characters.

    Returns:
        LeaveRequest: Status ``pending``.

    Raises:
        ValidationError: Bad kind, day, note, or that day is already
            pending or approved.

    Side effects:
        Writes one row. Texts the people who can decide.
    """
    if kind not in (LeaveRequest.KIND_LEAVE, LeaveRequest.KIND_SICK):
        raise ValidationError({'kind': 'Choose a day off or a sick day.'})
    text = (note or '').strip()
    if len(text) > NOTE_MAX:
        raise ValidationError({'note': f'Keep the note to {NOTE_MAX} characters.'})
    _check_day(kind, day)
    if kind == LeaveRequest.KIND_LEAVE:
        _require_leave_allowance(user, day)
    if LeaveRequest.objects.filter(
        user=user,
        day=day,
        status__in=(LeaveRequest.STATUS_PENDING, LeaveRequest.STATUS_APPROVED),
    ).exists():
        raise ValidationError({'day': 'That day is already requested or approved.'})
    leave = LeaveRequest.objects.create(
        user=user,
        kind=kind,
        day=day,
        note=text,
        status=LeaveRequest.STATUS_PENDING,
    )
    _notify_request(leave)
    return leave


def decide_leave(actor, leave: LeaveRequest, *, decision: str, note: str = '') -> LeaveRequest:
    """
    Approve or reject a pending day.

    Args:
        actor: Manager or director. Not the requester.
        leave: Pending request.
        decision: ``approved`` or ``rejected``.
        note: Optional reason, 0–300 characters.

    Returns:
        LeaveRequest: Updated row.

    Raises:
        PermissionDenied: This person cannot decide this request.
        ValidationError: It is not pending, or the decision is unknown.

    Side effects:
        Writes the decision. Texts the employee and the directors.
    """
    if decision not in (LeaveRequest.STATUS_APPROVED, LeaveRequest.STATUS_REJECTED):
        raise ValidationError({'decision': 'Choose approved or rejected.'})
    text = (note or '').strip()
    if len(text) > NOTE_MAX:
        raise ValidationError({'note': f'Keep the note to {NOTE_MAX} characters.'})
    if leave.status != LeaveRequest.STATUS_PENDING:
        raise ValidationError({'status': 'This request is already decided.'})
    if not may_decide(actor, leave):
        raise PermissionDenied('You cannot decide this request.')
    leave.status = decision
    leave.decision_note = text
    leave.decided_by = actor
    leave.decided_at = timezone.now()
    leave.save(update_fields=['status', 'decision_note', 'decided_by', 'decided_at'])
    _notify_decision(leave)
    return leave


def _directors(except_user=None):
    """
    Active directors and super admins, at most 30.

    Args:
        except_user: User to skip, or None.

    Returns:
        list[User]. No writes.
    """
    qs = User.objects.filter(is_active=True).filter(
        Q(is_superuser=True)
        | Q(profile__role='director')
        | Q(profile__custom_role__name=ROLE_DIRECTOR)
    ).distinct()
    if except_user is not None:
        qs = qs.exclude(pk=except_user.pk)
    return list(qs.select_related('profile')[:SMS_MAX])


def _managers(except_user=None):
    """
    Active managers who are not directors, at most 30.

    Args:
        except_user: User to skip, or None.

    Returns:
        list[User]. No writes.
    """
    qs = User.objects.filter(is_active=True).filter(
        Q(profile__role='manager') | Q(profile__custom_role__name=ROLE_MANAGER)
    ).exclude(is_superuser=True).exclude(profile__role='director').exclude(
        profile__custom_role__name=ROLE_DIRECTOR
    ).distinct()
    if except_user is not None:
        qs = qs.exclude(pk=except_user.pk)
    return list(qs.select_related('profile')[:SMS_MAX])


def _phone(user) -> str:
    """
    Profile phone, or a blank string.

    Args:
        user: Django user.

    Returns:
        str of 0–20 characters. No writes.
    """
    profile = _profile(user)
    if profile is None:
        return ''
    return (profile.phone_number or '').strip()[:20]


def _send(users, body: str, created_by) -> None:
    """
    Queue one SMS per person who has a phone.

    Args:
        users: Iterable of users. At most 30 are used.
        body: Message, 1–320 characters. Must not contain a phone number
            supplied by this function.
        created_by: Stored on the outbox row.

    Returns:
        None. A missing phone or a send failure does not raise.
    """
    from messaging.customer_notify import dispatch_outbox
    from messaging.models import MessageOutbox

    seen = set()
    text = (body or '').strip()[:320]
    if not text:
        return
    for user in list(users)[:SMS_MAX]:
        phone = _phone(user)
        if not phone or phone in seen:
            continue
        seen.add(phone)
        msg = MessageOutbox.objects.create(
            to_phone=phone,
            body=text,
            template_key='leave_decision',
            created_by=created_by,
        )

        def _later(row=msg):
            try:
                dispatch_outbox(row)
            except Exception:
                logger.exception('Leave SMS failed for outbox %s', row.pk)

        transaction.on_commit(_later)


def _kind_label(kind: str) -> str:
    """
    Human words for a kind code.

    Args:
        kind: ``leave`` or ``sick``.

    Returns:
        str. No writes.
    """
    if kind == LeaveRequest.KIND_SICK:
        return 'sick day'
    return 'day off'


def _notify_request(leave: LeaveRequest) -> None:
    """
    Tell the people who can decide that a day is waiting.

    Args:
        leave: New pending request.

    Returns:
        None. Texts managers, or directors when the requester is a manager.
    """
    people = _directors(leave.user) if is_manager(leave.user) or is_director(leave.user) else _managers(leave.user)
    if not people and (is_manager(leave.user) or not is_director(leave.user)):
        people = _directors(leave.user)
    day = leave.day.strftime('%d %b %Y')
    _send(
        people,
        f'{_name(leave.user)} asked for a {_kind_label(leave.kind)} on {day}. Open Leave in the shop.',
        leave.user,
    )


def _notify_decision(leave: LeaveRequest) -> None:
    """
    Tell the employee and the directors what was decided.

    Args:
        leave: Approved or rejected request.

    Returns:
        None.
    """
    day = leave.day.strftime('%d %b %Y')
    word = 'approved' if leave.status == LeaveRequest.STATUS_APPROVED else 'rejected'
    label = _kind_label(leave.kind)
    _send(
        [leave.user],
        f'Your {label} on {day} was {word}.',
        leave.decided_by,
    )
    _send(
        _directors(),
        f'{_name(leave.user)}\'s {label} on {day} was {word} by {_name(leave.decided_by)}.',
        leave.decided_by,
    )


def _clamp_days(raw) -> int:
    """
    Keep a day-off allowance inside 0–31.

    Args:
        raw: A whole number.

    Returns:
        int: 0–31.

    Raises:
        ValidationError: Not a whole number, or outside 0–31.
    """
    try:
        days = int(raw)
    except (TypeError, ValueError):
        raise ValidationError({'monthly_leave_days': 'Enter a whole number from 0 to 31.'})
    if days < 0 or days > LEAVE_DAY_MAX:
        raise ValidationError({'monthly_leave_days': 'Enter a whole number from 0 to 31.'})
    return days


def leave_limit(user) -> tuple:
    """
    How many day-off requests this person may have in one month.

    Args:
        user: The employee.

    Returns:
        tuple: ``(days, custom)``. ``days`` is 0–31. ``custom`` is True when
        this person has their own number. No writes.
    """
    from accounts.models import UserProfile

    row = UserProfile.objects.filter(user_id=getattr(user, 'pk', None)).values('monthly_leave_days').first()
    custom = None if row is None else row['monthly_leave_days']
    if custom is not None:
        return max(0, min(LEAVE_DAY_MAX, int(custom))), True
    from employees.module_settings import employees_monthly_leave_days

    return employees_monthly_leave_days(), False


def leave_used(user, day) -> int:
    """
    Day-off requests already pending or approved in that month.

    Args:
        user: The employee.
        day: Any date in the month being counted.

    Returns:
        int: 0–31. Sick days and rejected days are not counted. No writes.
    """
    return LeaveRequest.objects.filter(
        user=user,
        kind=LeaveRequest.KIND_LEAVE,
        status__in=(LeaveRequest.STATUS_PENDING, LeaveRequest.STATUS_APPROVED),
        day__year=day.year,
        day__month=day.month,
    ).count()


def allowance_payload(user, day) -> dict:
    """
    This person's day-off allowance for the month of ``day``.

    Args:
        user: The employee.
        day: datetime.date inside the month.

    Returns:
        dict: ``limit`` 0–31, ``used``, ``remaining``, ``custom``, and
        ``month`` as ``YYYY-MM``. No phone. No writes.
    """
    limit, custom = leave_limit(user)
    used = leave_used(user, day)
    return {
        'limit': limit,
        'used': used,
        'remaining': max(0, limit - used),
        'custom': custom,
        'month': f'{day.year:04d}-{day.month:02d}',
    }


def _require_leave_allowance(user, day) -> None:
    """
    Refuse a day off that would pass the monthly number.

    Args:
        user: The employee.
        day: The requested day.

    Returns:
        None.

    Raises:
        ValidationError: Pending and approved days in that month already
        reach the allowance.
    """
    limit, _custom = leave_limit(user)
    used = leave_used(user, day)
    if used >= limit:
        raise ValidationError({
            'day': (
                f'{day.strftime("%B")} allows {limit} day off. '
                f'{used} already requested or approved.'
            ),
        })


def user_may_configure_leave(user) -> bool:
    """
    True when this person may change the monthly number.

    Args:
        user: Signed-in user.

    Returns:
        bool. Super Admin and anyone with ``employees.leave_approve``.
        No writes.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    profile = _profile(user)
    if profile is None:
        return False
    return profile.has_permission('employees', 'leave_approve')


def allowance_people() -> list:
    """
    Active people and the day-off number that applies to each.

    Returns:
        list[dict]: At most 200 rows with ``id``, ``name``, ``monthly_leave_days``
        (null when they use the shop number), and ``effective`` 0–31.
        No phone numbers. No writes.
    """
    rows = []
    people = (
        User.objects.filter(is_active=True, profile__isnull=False)
        .select_related('profile')
        .order_by('first_name', 'username')[:PEOPLE_MAX]
    )
    for person in people:
        limit, custom = leave_limit(person)
        rows.append({
            'id': person.id,
            'name': _name(person),
            'monthly_leave_days': person.profile.monthly_leave_days if custom else None,
            'effective': limit,
        })
    return rows


def set_shop_leave_days(actor, days: int) -> int:
    """
    Set the day-off number for everyone who does not have their own.

    Args:
        actor: Manager or director. Stored as the setting editor.
        days: 0–31.

    Returns:
        int: The saved number.

    Raises:
        ValidationError: Outside 0–31.

    Side effects:
        Writes the employees.monthly_leave_days setting.
    """
    from settings.settings_service import SettingsService

    value = _clamp_days(days)
    SettingsService.set('employees', 'monthly_leave_days', value, user=actor)
    return value


def set_person_leave_days(actor, user_id, days) -> dict:
    """
    Set or clear one person's day-off number.

    Args:
        actor: Unused except to keep the call explicit. Permission is
            checked by the view.
        user_id: Active user id.
        days: 0–31, or None to use the shop number again.

    Returns:
        dict: That person's allowance row. No phone.

    Raises:
        ValidationError: Unknown person, or a number outside 0–31.

    Side effects:
        Writes ``UserProfile.monthly_leave_days``.
    """
    del actor
    try:
        person = User.objects.select_related('profile').get(pk=int(user_id), is_active=True)
    except (User.DoesNotExist, TypeError, ValueError):
        raise ValidationError({'user_id': 'Choose a person from the list.'})
    profile = _profile(person)
    if profile is None:
        raise ValidationError({'user_id': 'Choose a person from the list.'})
    if days is None or days == '':
        profile.monthly_leave_days = None
    else:
        profile.monthly_leave_days = _clamp_days(days)
    profile.save(update_fields=['monthly_leave_days'])
    limit, custom = leave_limit(person)
    return {
        'id': person.id,
        'name': _name(person),
        'monthly_leave_days': profile.monthly_leave_days if custom else None,
        'effective': limit,
    }


def row_payload(leave: LeaveRequest, viewer) -> dict:
    """
    One request for the API.

    Args:
        leave: Saved request.
        viewer: Signed-in user. Used only for ``can_decide``.

    Returns:
        dict. No phone numbers. No writes.
    """
    return {
        'id': leave.id,
        'kind': leave.kind,
        'day': leave.day.isoformat(),
        'note': leave.note,
        'status': leave.status,
        'requester_name': _name(leave.user),
        'decision_note': leave.decision_note,
        'decided_by_name': _name(leave.decided_by) if leave.decided_by_id else '',
        'can_decide': leave.status == LeaveRequest.STATUS_PENDING and may_decide(viewer, leave),
    }
