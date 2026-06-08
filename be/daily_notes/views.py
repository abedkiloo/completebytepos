from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import RequireModuleEnabled, RequirePermPerAction
from settings.models import ModuleSettings
from utils.audit_helpers import (
    audited_perform_create,
    _module_for,
    _snapshot,
)
from utils.audit import log_audit
from utils.audit_mixin import AuditedModelViewSetMixin

from .access import user_may_access_daily_notes, user_may_view_all_daily_notes
from .models import DailyNote
from .serializers import DailyNoteSerializer
from .services import DailyNoteService

DAILY_NOTES_PERMS = RequirePermPerAction(
    'daily_notes',
    {
        'list': 'view',
        'retrieve': 'view',
        'create': 'create',
        'update': 'update',
        'partial_update': 'update',
        'destroy': 'update',
        'recent_dates': 'view',
    },
)


class DailyNoteViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = DailyNoteSerializer
    permission_classes = [IsAuthenticated, RequireModuleEnabled('daily_notes'), DAILY_NOTES_PERMS]
    audit_module = 'daily_notes'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.note_service = DailyNoteService()

    def _module_disabled(self):
        return not ModuleSettings.is_module_enabled('daily_notes')

    def _access_denied(self):
        return Response(
            {'error': 'Daily notes are not available for your role.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    def get_queryset(self):
        if self._module_disabled():
            return DailyNote.objects.none()
        if not user_may_access_daily_notes(self.request.user):
            return DailyNote.objects.none()

        filters = {}
        params = self.request.query_params
        if 'note_date' in params:
            filters['note_date'] = params.get('note_date')
        if 'author' in params:
            filters['author'] = params.get('author')
        if 'search' in params:
            filters['search'] = params.get('search')

        return self.note_service.build_queryset(
            user=self.request.user,
            view_all=user_may_view_all_daily_notes(self.request.user),
            filters=filters,
        )

    def list(self, request, *args, **kwargs):
        if not user_may_access_daily_notes(request.user):
            return self._access_denied()
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        audited_perform_create(
            self,
            serializer,
            author=self.request.user,
        )

    def update(self, request, *args, **kwargs):
        note = self.get_object()
        if note.author_id != request.user.id and not request.user.is_superuser:
            return Response(
                {'error': 'You can only edit your own notes.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        from accounts.models import AuditLog

        note = self.get_object()
        if note.author_id != request.user.id and not request.user.is_superuser:
            return Response(
                {'error': 'You can only delete your own notes.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        snapshot = _snapshot(note)
        object_repr = snapshot.get('__str__', str(note)[:255])
        module = _module_for(self, note)
        note.delete()
        log_audit(
            request,
            AuditLog.ACTION_DELETE,
            None,
            module=module,
            object_repr=object_repr,
            changes={'__deleted__': snapshot},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='recent-dates')
    def recent_dates(self, request):
        if not user_may_access_daily_notes(request.user):
            return self._access_denied()
        dates = self.note_service.recent_dates(
            user=request.user,
            view_all=user_may_view_all_daily_notes(request.user),
        )
        return Response({'dates': dates})
