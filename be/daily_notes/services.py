from __future__ import annotations

from django.db.models import Q

from .models import DailyNote, DailyTask


def _scoped_queryset(model, *, user, view_all: bool):
    qs = model.objects.select_related('author', 'author__profile')
    if not view_all:
        qs = qs.filter(author=user)
    return qs


def _apply_common_filters(qs, *, date_field: str, filters: dict | None, view_all: bool):
    filters = filters or {}
    day = filters.get('task_date') or filters.get('note_date')
    if day:
        qs = qs.filter(**{date_field: day})

    author_id = filters.get('author')
    if author_id and view_all:
        qs = qs.filter(author_id=author_id)

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

    return qs


class DailyNoteService:
    def build_queryset(self, *, user, view_all: bool, filters: dict | None = None):
        qs = _scoped_queryset(DailyNote, user=user, view_all=view_all)
        qs = _apply_common_filters(qs, date_field='note_date', filters=filters, view_all=view_all)
        return qs.order_by('-note_date', '-created_at')

    def recent_dates(self, *, user, view_all: bool, limit: int = 30):
        return recent_activity_dates(user=user, view_all=view_all, limit=limit)


class DailyTaskService:
    def build_queryset(self, *, user, view_all: bool, filters: dict | None = None):
        qs = _scoped_queryset(DailyTask, user=user, view_all=view_all)
        qs = _apply_common_filters(qs, date_field='task_date', filters=filters, view_all=view_all)
        return qs.order_by('is_done', '-created_at')

    def recent_dates(self, *, user, view_all: bool, limit: int = 30):
        return recent_activity_dates(user=user, view_all=view_all, limit=limit)


def recent_activity_dates(*, user, view_all: bool, limit: int = 30):
    """Distinct dates that have notes or tasks."""
    note_qs = DailyNote.objects.all()
    task_qs = DailyTask.objects.all()
    if not view_all:
        note_qs = note_qs.filter(author=user)
        task_qs = task_qs.filter(author=user)

    dates = set(note_qs.values_list('note_date', flat=True).distinct())
    dates.update(task_qs.values_list('task_date', flat=True).distinct())
    return sorted(dates, reverse=True)[:limit]
