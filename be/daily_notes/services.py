"""
Daily notes listing, assignment fan-out, and desk filters.

Public entry points:
    - ``DailyNoteService`` / ``DailyTaskService`` — scoped querysets
    - ``create_notes_for_assignees`` — role/all-staff broadcast (cap 500 targets)
    - ``parse_filter_date`` / ``carried_over_days`` / ``recent_activity_dates``

Side effects: ``build_queryset`` may auto-close stale approval notices via
``approval_notice`` helpers. ``create_notes_for_assignees`` bulk-inserts rows.
"""
from __future__ import annotations

import uuid
from datetime import date

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from .models import DailyNote, DailyTask


def parse_filter_date(value):
    """
    Parse ISO calendar dates from query params or ``date`` instances.

    Args:
        value: ``YYYY-MM-DD`` string (first 10 chars used), ``date``, or empty.

    Returns:
        A ``date`` or ``None`` when missing or invalid.
    """
    if value in (None, ''):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def carried_over_days(*, origin, as_of=None, is_done=False) -> int:
    """
    Count days an open item has carried past its scheduled date.

    Args:
        origin: Original ``note_date`` / ``task_date`` (ISO string or ``date``).
        as_of: Comparison day; defaults to ``timezone.localdate()``.
        is_done: When ``True``, returns ``0`` (completed items do not carry).

    Returns:
        Positive day count when ``as_of > origin``; otherwise ``0``.
    """
    if is_done or origin is None:
        return 0
    as_of = parse_filter_date(as_of) or timezone.localdate()
    origin = parse_filter_date(origin)
    if origin is None:
        return 0
    delta = (as_of - origin).days
    return delta if delta > 0 else 0


def users_with_role(role):
    """
    List active users assigned a custom ``accounts.Role``.

    Args:
        role: ``Role`` instance or ``None``.

    Returns:
        Ordered list of ``User`` rows (empty when ``role`` is ``None``).
    """
    if role is None:
        return []
    return list(
        User.objects.filter(is_active=True, profile__custom_role=role)
        .select_related('profile', 'profile__custom_role')
        .order_by('id')
    )


def active_staff_users():
    """
    Return all active Django users for broadcast assignment.

    Returns:
        List ordered by user ``id`` (no role filter).
    """
    return list(
        User.objects.filter(is_active=True)
        .select_related('profile', 'profile__custom_role')
        .order_by('id')
    )


def create_notes_for_assignees(
    *,
    author,
    note_date,
    content,
    title='',
    is_sticky=False,
    is_done=False,
    in_progress=False,
    priority=None,
    assigned_to=None,
    assigned_role=None,
    assign_to_all=False,
):
    """
    Create one or many ``DailyNote`` rows for assignees.

    Fan-out: ``assign_to_all`` → every active user; ``assigned_role`` → role
    members; ``assigned_to`` → single user; sticky without assignee → author;
    otherwise one note with ``assigned_to=None``. Caps targets at 500 users.

    Args:
        author: Note author (required).
        note_date: Calendar day for the note.
        content: Body text (required on model).
        title: Optional headline (max 200).
        is_sticky: Must-tick gate for assignee.
        is_done: When ``True``, marks done at creation time.
        in_progress: Board column hint when not done.
        priority: ``high`` / ``medium`` / ``low``; defaults to medium.
        assigned_to: Single assignee override.
        assigned_role: Role fan-out when set.
        assign_to_all: Broadcast to all active staff when ``True``.

    Returns:
        List of created ``DailyNote`` instances (empty when no targets).
    """
    from daily_notes.models import PRIORITY_MEDIUM
    if assign_to_all:
        targets = active_staff_users()
        role = None
    elif assigned_to is not None:
        targets = [assigned_to]
        role = None
    elif assigned_role is not None:
        targets = users_with_role(assigned_role)
        role = assigned_role
    elif is_sticky:
        targets = [author]
        role = None
    else:
        targets = [None]
        role = None

    # Guard against accidental fan-out across a huge staff table.
    max_targets = 500
    if len(targets) > max_targets:
        targets = targets[:max_targets]

    group = uuid.uuid4() if len(targets) > 1 else None
    notes = []
    done_at = timezone.now() if is_done else None
    for user in targets:
        note = DailyNote(
            note_date=note_date,
            title=title,
            content=content,
            priority=priority or PRIORITY_MEDIUM,
            is_sticky=is_sticky,
            in_progress=False if is_done else bool(in_progress),
            author=author,
            assigned_to=user,
            assigned_role=role,
            assignment_group=group,
        )
        if is_done:
            note.mark_done(done=True, at=done_at)
        else:
            note.is_done = False
            note.completed_at = None
        notes.append(note)
    if not notes:
        return []
    # One INSERT instead of N round-trips when broadcasting to a role / all staff.
    return list(DailyNote.objects.bulk_create(notes))


def _scoped_queryset(model, *, user, view_all: bool):
    qs = model.objects.select_related('author', 'author__profile')
    related = [field.name for field in model._meta.get_fields() if getattr(field, 'name', None)]
    if 'assigned_to' in related:
        qs = qs.select_related('assigned_to', 'assigned_to__profile')
    if model is DailyNote:
        qs = qs.select_related('assigned_role').prefetch_related('checklist_items')
    if not view_all:
        if model is DailyNote:
            qs = qs.filter(Q(author=user) | Q(assigned_to=user))
        else:
            qs = qs.filter(author=user)
    return qs


def _scoped_task_queryset(*, user, view_all: bool):
    qs = DailyTask.objects.select_related(
        'author',
        'author__profile',
        'assigned_to',
        'assigned_to__profile',
    )
    if not view_all:
        qs = qs.filter(assigned_to=user)
    return qs


def _apply_common_filters(qs, *, date_field: str, filters: dict | None, view_all: bool):
    filters = filters or {}
    day_raw = filters.get('task_date') or filters.get('note_date')
    day = parse_filter_date(day_raw)
    status = filters.get('status')
    if day is not None:
        # Open items stay on every later day until they are acted on.
        # Completed items stay on the day they belong to.
        if status == 'done':
            qs = qs.filter(**{date_field: day, 'is_done': True})
        else:
            qs = qs.filter(
                Q(**{date_field: day})
                | Q(is_done=False, **{f'{date_field}__lt': day})
            )
            if status == 'open':
                qs = qs.filter(is_done=False)
    else:
        if day_raw:
            qs = qs.filter(**{date_field: day_raw})
        if status == 'done':
            qs = qs.filter(is_done=True)
        elif status == 'open':
            qs = qs.filter(is_done=False)

    author_id = filters.get('author')
    if author_id and view_all:
        qs = qs.filter(author_id=author_id)

    assignee_id = filters.get('assigned_to')
    if assignee_id and view_all:
        qs = qs.filter(assigned_to_id=assignee_id)

    # Desk “Person” filter: notes authored by or assigned to them; tasks assigned to them.
    person_id = filters.get('person')
    if person_id and view_all:
        if getattr(qs.model, '__name__', '') == 'DailyNote':
            qs = qs.filter(Q(assigned_to_id=person_id) | Q(author_id=person_id))
        else:
            qs = qs.filter(assigned_to_id=person_id)

    search = (filters.get('search') or '').strip()
    if search:
        if date_field == 'note_date':
            qs = qs.filter(Q(title__icontains=search) | Q(content__icontains=search))
        else:
            qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))

    if getattr(qs.model, '__name__', '') == 'DailyNote':
        kind = (filters.get('kind') or '').strip().lower()
        if kind == 'sticky':
            qs = qs.filter(is_sticky=True)
        elif kind == 'general':
            qs = qs.filter(is_sticky=False)

        is_sticky = filters.get('is_sticky')
        if is_sticky in (True, 'true', 'True', '1', 1):
            qs = qs.filter(is_sticky=True)
        elif is_sticky in (False, 'false', 'False', '0', 0):
            qs = qs.filter(is_sticky=False)

    return qs


class DailyNoteService:
    """Scoped note listings with desk filters and stale-notice cleanup."""

    def build_queryset(self, *, user, view_all: bool, filters: dict | None = None):
        """
        Build the note queryset visible to ``user`` or all staff.

        Args:
            user: Acting user for scope when ``view_all`` is ``False``.
            view_all: When ``True``, managers see all notes; filters may use
                ``author`` / ``assigned_to`` / ``person``.
            filters: Optional dict (``note_date``, ``status``, ``search``, ``kind``,
                ``is_sticky``, etc.).

        Returns:
            Ordered ``DailyNote`` queryset. Runs ``complete_stale_approval_notices``
            first (side effect: may close resolved cards).
        """
        from daily_notes.approval_notice import complete_stale_approval_notices

        complete_stale_approval_notices(user=None if view_all else user)
        from daily_notes.models import priority_sort_case

        qs = _scoped_queryset(DailyNote, user=user, view_all=view_all)
        qs = _apply_common_filters(qs, date_field='note_date', filters=filters, view_all=view_all)
        priority_filter = (filters or {}).get('priority')
        if priority_filter in ('high', 'medium', 'low'):
            qs = qs.filter(priority=priority_filter)
        return qs.order_by(
            '-is_sticky',
            priority_sort_case(),
            'is_done',
            '-note_date',
            '-created_at',
        )

    def blocking_for_user(self, *, user, limit: int = 50):
        """
        Open notes assigned to this user (sticky first) for login gating.

        Args:
            user: Assignee to match.
            limit: Max rows when not ``None``; slice applied after ordering.

        Returns:
            ``DailyNote`` queryset (possibly sliced). Runs stale-notice cleanup
            for this user first.
        """
        from daily_notes.approval_notice import complete_stale_approval_notices

        complete_stale_approval_notices(user=user)
        qs = (
            DailyNote.objects.filter(
                is_done=False,
                assigned_to=user,
            )
            .select_related(
                'author',
                'author__profile',
                'assigned_to',
                'assigned_to__profile',
                'assigned_role',
            )
            .order_by('-is_sticky', 'note_date', '-created_at')
        )
        if limit is not None:
            return qs[:limit]
        return qs

    def recent_dates(self, *, user, view_all: bool, limit: int = 30):
        """
        Distinct calendar dates with note or task activity.

        Args:
            user: Scope user when ``view_all`` is ``False``.
            view_all: Include org-wide dates when ``True``.
            limit: Max dates returned (newest first).

        Returns:
            List of ``date`` objects (length ≤ ``limit``).
        """
        return recent_activity_dates(user=user, view_all=view_all, limit=limit)


class DailyTaskService:
    """Task listings, pending badges, and stale sale-notice cleanup."""

    def build_queryset(self, *, user, view_all: bool, filters: dict | None = None):
        """
        Build task queryset for desk views.

        Args:
            user: Assignee scope when not ``view_all``.
            view_all: When ``True``, all tasks; enables ``author`` filters.
            filters: Same shape as notes but uses ``task_date``.

        Returns:
            Ordered ``DailyTask`` queryset after stale-notice cleanup.
        """
        from daily_notes.approval_notice import complete_stale_sale_notice_tasks

        complete_stale_sale_notice_tasks(user=None if view_all else user)
        qs = _scoped_task_queryset(user=user, view_all=view_all)
        qs = _apply_common_filters(qs, date_field='task_date', filters=filters, view_all=view_all)
        from daily_notes.models import priority_sort_case

        priority_filter = (filters or {}).get('priority')
        if priority_filter in ('high', 'medium', 'low'):
            qs = qs.filter(priority=priority_filter)
        return qs.order_by(priority_sort_case(), 'is_done', '-created_at')

    def pending_for_user(self, *, user, limit: int = 50, cleanup_stale: bool = True):
        """
        Open tasks assigned to ``user`` for widgets and banners.

        Args:
            user: Assignee filter.
            limit: Max rows (default 50).
            cleanup_stale: When ``True``, closes resolved approval tasks first.

        Returns:
            Sliced queryset of open tasks ordered by date.
        """
        if cleanup_stale:
            from daily_notes.approval_notice import complete_stale_sale_notice_tasks

            complete_stale_sale_notice_tasks(user=user)
        return (
            DailyTask.objects.filter(assigned_to=user, is_done=False)
            .select_related('author', 'author__profile', 'assigned_to', 'assigned_to__profile')
            .order_by('task_date', '-created_at')[:limit]
        )

    def pending_count_for_user(self, *, user) -> int:
        """
        Count open tasks for badge polling without stale cleanup.

        Args:
            user: Assignee filter.

        Returns:
            Non-negative integer count.
        """
        return DailyTask.objects.filter(assigned_to=user, is_done=False).count()

    def recent_dates(self, *, user, view_all: bool, limit: int = 30):
        """See ``DailyNoteService.recent_dates``."""
        return recent_activity_dates(user=user, view_all=view_all, limit=limit)


def recent_activity_dates(*, user, view_all: bool, limit: int = 30):
    """
    Distinct calendar dates that have notes or tasks.

    Args:
        user: Scope when ``view_all`` is ``False``.
        view_all: Union of all note/task dates when ``True``.
        limit: Cap on returned dates (newest first).

    Returns:
        Sorted list of ``date`` (descending, length ≤ ``limit``).
    """
    note_qs = DailyNote.objects.all()
    task_qs = DailyTask.objects.all()
    if not view_all:
        note_qs = note_qs.filter(Q(author=user) | Q(assigned_to=user))
        task_qs = task_qs.filter(assigned_to=user)

    dates = set(note_qs.values_list('note_date', flat=True).distinct())
    dates.update(task_qs.values_list('task_date', flat=True).distinct())
    return sorted(dates, reverse=True)[:limit]
