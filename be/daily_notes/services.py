from __future__ import annotations

from django.db.models import Q

from .models import DailyNote


class DailyNoteService:
    def build_queryset(self, *, user, view_all: bool, filters: dict | None = None):
        qs = DailyNote.objects.select_related('author', 'author__profile')
        if not view_all:
            qs = qs.filter(author=user)

        filters = filters or {}
        note_date = filters.get('note_date')
        if note_date:
            qs = qs.filter(note_date=note_date)

        author_id = filters.get('author')
        if author_id and view_all:
            qs = qs.filter(author_id=author_id)

        search = (filters.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(content__icontains=search)
            )

        return qs.order_by('-note_date', '-created_at')

    def recent_dates(self, *, user, view_all: bool, limit: int = 30):
        qs = DailyNote.objects.all()
        if not view_all:
            qs = qs.filter(author=user)
        return list(
            qs.values_list('note_date', flat=True)
            .distinct()
            .order_by('-note_date')[:limit]
        )
