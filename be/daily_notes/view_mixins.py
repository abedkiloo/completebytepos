"""Shared author-scoped behaviour for daily notes and tasks."""

from rest_framework import status
from rest_framework.response import Response

from accounts.models import AuditLog
from settings.models import ModuleSettings
from utils.audit import log_audit
from utils.audit_helpers import _module_for, _snapshot, audited_perform_create
from utils.audit_mixin import AuditedModelViewSetMixin

from .access import user_may_access_daily_notes, user_may_view_all_daily_notes


class DailyAuthorScopedViewSetMixin(AuditedModelViewSetMixin):
    audit_module = 'daily_notes'

    date_param = 'note_date'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entry_service = None

    def _module_disabled(self):
        return not ModuleSettings.is_module_enabled('daily_notes')

    def _access_denied(self):
        return Response(
            {'error': 'Daily notes are not available for your role.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    def _parse_filters(self):
        filters = {}
        params = getattr(self.request, 'query_params', self.request.GET)
        if self.date_param in params:
            filters[self.date_param] = params.get(self.date_param)
        if 'author' in params:
            filters['author'] = params.get('author')
        if 'search' in params:
            filters['search'] = params.get('search')
        if 'status' in params:
            filters['status'] = params.get('status')
        return filters

    def get_queryset(self):
        if self._module_disabled():
            return self.queryset.model.objects.none()
        if not user_may_access_daily_notes(self.request.user):
            return self.queryset.model.objects.none()
        return self.entry_service.build_queryset(
            user=self.request.user,
            view_all=user_may_view_all_daily_notes(self.request.user),
            filters=self._parse_filters(),
        )

    def list(self, request, *args, **kwargs):
        if not user_may_access_daily_notes(request.user):
            return self._access_denied()
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        audited_perform_create(self, serializer, author=self.request.user)

    def _author_may_modify(self, instance) -> bool:
        user = self.request.user
        return instance.author_id == user.id or user.is_superuser

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not self._author_may_modify(instance):
            return Response(
                {'error': 'You can only edit your own entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not self._author_may_modify(instance):
            return Response(
                {'error': 'You can only delete your own entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        snapshot = _snapshot(instance)
        object_repr = snapshot.get('__str__', str(instance)[:255])
        module = _module_for(self, instance)
        instance.delete()
        log_audit(
            request,
            AuditLog.ACTION_DELETE,
            None,
            module=module,
            object_repr=object_repr,
            changes={'__deleted__': snapshot},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
