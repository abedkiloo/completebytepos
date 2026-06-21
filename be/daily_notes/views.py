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
        'pending': 'view',
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

    def _may_edit_task(self, instance) -> bool:
        user = self.request.user
        if user.is_superuser:
            return True
        if instance.author_id == user.id:
            return True
        return user_may_view_all_daily_notes(user)

    def _may_toggle_task(self, instance) -> bool:
        user = self.request.user
        if user.is_superuser:
            return True
        if instance.assigned_to_id == user.id:
            return True
        if instance.author_id == user.id:
            return True
        return False

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not self._may_edit_task(instance):
            return Response(
                {'error': 'You can only edit tasks you created or when viewing all staff tasks.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super(DailyAuthorScopedViewSetMixin, self).update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not self._may_edit_task(instance):
            return Response(
                {'error': 'You can only delete tasks you created or when viewing all staff tasks.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super(DailyAuthorScopedViewSetMixin, self).destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='toggle-done')
    def toggle_done(self, request, pk=None):
        if not user_may_access_daily_notes(request.user):
            return self._access_denied()
        task = self.get_object()
        if not self._may_toggle_task(task):
            return Response(
                {'error': 'You can only update tasks assigned to you.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        task.is_done = not task.is_done
        task.mark_done(done=task.is_done)
        task.save(update_fields=['is_done', 'completed_at', 'updated_at'])
        return Response(DailyTaskSerializer(task).data)

    @action(detail=False, methods=['get'], url_path='pending')
    def pending(self, request):
        if not user_may_access_daily_notes(request.user):
            return self._access_denied()
        tasks = self.entry_service.pending_for_user(user=request.user)
        return Response(DailyTaskSerializer(tasks, many=True).data)
