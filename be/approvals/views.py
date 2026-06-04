from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.sensitive_edits import user_may_edit_financial_fields
from approvals.models import PendingChange
from approvals.serializers import (
    ApproveChangeSerializer,
    PendingChangeSerializer,
    RejectChangeSerializer,
)
from approvals.service import approve_change, reject_change


class PendingChangeViewSet(viewsets.ReadOnlyModelViewSet):
    """Checker queue: list/retrieve pending and completed proposals."""

    queryset = PendingChange.objects.all().select_related('made_by', 'checked_by')
    serializer_class = PendingChangeSerializer
    permission_classes = [IsAuthenticated]

    def _require_checker(self, request):
        if not user_may_edit_financial_fields(request.user):
            raise PermissionDenied('Checker access required.')

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        action_type = self.request.query_params.get('action_type')
        if action_type:
            qs = qs.filter(action_type=action_type)
        entity_type = self.request.query_params.get('entity_type')
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        return qs

    def list(self, request, *args, **kwargs):
        self._require_checker(request)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        self._require_checker(request)
        return super().retrieve(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """All rows awaiting checker action."""
        self._require_checker(request)
        qs = self.get_queryset().filter(status=PendingChange.STATUS_PENDING)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        self._require_checker(request)
        change = self.get_object()
        body = ApproveChangeSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            approve_change(
                change,
                request.user,
                request=request,
                extreme_price_confirmed=body.validated_data.get(
                    'extreme_price_confirmed', False
                ),
            )
        except DjangoValidationError as exc:
            if hasattr(exc, 'message_dict'):
                return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        change.refresh_from_db()
        return Response(PendingChangeSerializer(change).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        self._require_checker(request)
        change = self.get_object()
        body = RejectChangeSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            reject_change(
                change,
                request.user,
                body.validated_data['rejection_reason'],
                request=request,
            )
        except DjangoValidationError as exc:
            if hasattr(exc, 'message_dict'):
                return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        change.refresh_from_db()
        return Response(PendingChangeSerializer(change).data)
