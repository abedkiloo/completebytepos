from __future__ import annotations

import uuid

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from .models import DailyNote, DailyTask


def users_with_role(role):
    if role is None:
        return []
    return list(
        User.objects.filter(is_active=True, profile__custom_role=role)
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
    assigned_to=None,
    assigned_role=None,
):
    """One note for a person, or one copy per active user on a role."""
    if assigned_to is not None:
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

    group = uuid.uuid4() if len(targets) > 1 else None
    notes = []
    done_at = timezone.now() if is_done else None
    for user in targets:
        note = DailyNote(
            note_date=note_date,
            title=title,
            content=content,
            is_sticky=is_sticky,
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
        note.save()
        notes.append(note)
    return notes


def _scoped_queryset(model, *, user, view_all: bool):
    qs = model.objects.select_related('author', 'author__profile')
    related = [field.name for field in model._meta.get_fields() if getattr(field, 'name', None)]
    if 'assigned_to' in related:
        qs = qs.select_related('assigned_to', 'assigned_to__profile')
    if model is DailyNote:
        qs = qs.select_related('assigned_role')
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
    day = filters.get('task_date') or filters.get('note_date')
    if day:
        qs = qs.filter(**{date_field: day})

    author_id = filters.get('author')
    if author_id and view_all:
        qs = qs.filter(author_id=author_id)

    assignee_id = filters.get('assigned_to')
    if assignee_id and view_all:
        qs = qs.filter(assigned_to_id=assignee_id)

    search = (filters.get('search') or '').strip()
    if search:
        if date_field == 'note_date':
            qs = qs.filter(Q(title__icontains=search) | Q(content__icontains=search))
        else:
            qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))

    status = filters.get('status')
    if status == 'done':
        qs = qs.filter(is_done=True)
    elif status == 'open':
        qs = qs.filter(is_done=False)

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
    def build_queryset(self, *, user, view_all: bool, filters: dict | None = None):
        qs = _scoped_queryset(DailyNote, user=user, view_all=view_all)
        qs = _apply_common_filters(qs, date_field='note_date', filters=filters, view_all=view_all)
        return qs.order_by('-is_sticky', 'is_done', '-note_date', '-created_at')

    def blocking_for_user(self, *, user, limit: int = 50):
        qs = (
            DailyNote.objects.filter(
                is_sticky=True,
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
            .order_by('note_date', '-created_at')
        )
        if limit is not None:
            return qs[:limit]
        return qs

    def recent_dates(self, *, user, view_all: bool, limit: int = 30):
        return recent_activity_dates(user=user, view_all=view_all, limit=limit)


class DailyTaskService:
    def build_queryset(self, *, user, view_all: bool, filters: dict | None = None):
        qs = _scoped_task_queryset(user=user, view_all=view_all)
        qs = _apply_common_filters(qs, date_field='task_date', filters=filters, view_all=view_all)
        return qs.order_by('is_done', '-created_at')

    def pending_for_user(self, *, user, limit: int = 50):
        return (
            DailyTask.objects.filter(assigned_to=user, is_done=False)
            .select_related('author', 'author__profile', 'assigned_to', 'assigned_to__profile')
            .order_by('task_date', '-created_at')[:limit]
        )

    def recent_dates(self, *, user, view_all: bool, limit: int = 30):
        return recent_activity_dates(user=user, view_all=view_all, limit=limit)


def recent_activity_dates(*, user, view_all: bool, limit: int = 30):
    """Distinct dates that have notes or tasks."""
    note_qs = DailyNote.objects.all()
    task_qs = DailyTask.objects.all()
    if not view_all:
        note_qs = note_qs.filter(Q(author=user) | Q(assigned_to=user))
        task_qs = task_qs.filter(assigned_to=user)

    dates = set(note_qs.values_list('note_date', flat=True).distinct())
    dates.update(task_qs.values_list('task_date', flat=True).distinct())
    return sorted(dates, reverse=True)[:limit]
