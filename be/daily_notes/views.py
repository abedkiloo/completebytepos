from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import RequireModuleEnabled, RequirePermPerAction

from .access import user_may_access_daily_notes, user_may_view_all_daily_notes
from .models import DailyNote, DailyTask
from .serializers import DailyNoteSerializer, DailyTaskSerializer
from .services import DailyNoteService, DailyTaskService, recent_activity_dates
from .view_mixins import DailyAuthorScopedViewSetMixin

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
        'toggle_done': 'update',
    },
)


class DailyNoteViewSet(DailyAuthorScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = DailyNote.objects.all()
    serializer_class = DailyNoteSerializer
    permission_classes = [IsAuthenticated, RequireModuleEnabled('daily_notes'), DAILY_NOTES_PERMS]
    date_param = 'note_date'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entry_service = DailyNoteService()

    @action(detail=False, methods=['get'], url_path='recent-dates')
    def recent_dates(self, request):
        if not user_may_access_daily_notes(request.user):
            return self._access_denied()
        dates = recent_activity_dates(
            user=request.user,
            view_all=user_may_view_all_daily_notes(request.user),
        )
        return Response({'dates': dates})


class DailyTaskViewSet(DailyAuthorScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = DailyTask.objects.all()
    serializer_class = DailyTaskSerializer
    permission_classes = [IsAuthenticated, RequireModuleEnabled('daily_notes'), DAILY_NOTES_PERMS]
    date_param = 'task_date'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entry_service = DailyTaskService()

    @action(detail=True, methods=['post'], url_path='toggle-done')
    def toggle_done(self, request, pk=None):
        if not user_may_access_daily_notes(request.user):
            return self._access_denied()
        task = self.get_object()
        if not self._author_may_modify(task):
            return Response(
                {'error': 'You can only update your own tasks.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        task.is_done = not task.is_done
        task.mark_done(done=task.is_done)
        task.save(update_fields=['is_done', 'completed_at', 'updated_at'])
        return Response(DailyTaskSerializer(task).data)
