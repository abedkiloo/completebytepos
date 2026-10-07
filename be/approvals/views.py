from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.sensitive_edits import user_may_edit_financial_fields
from approvals.models import PendingChange
from approvals.serializers import (
    ApproveChangeSerializer,
    PendingChangeSerializer,
    RejectChangeSerializer,
    ResubmitChangeSerializer,
)
from approvals.service import approve_change, reject_change, resubmit_change


def _parse_query_date(raw, *, field_name):
    """YYYY-MM-DD (or blank) → date, else raise ValidationError."""
    if raw in (None, ''):
        return None
    day = parse_date(str(raw).strip())
    if day is None:
        raise ValidationError({field_name: 'Invalid date. Use YYYY-MM-DD.'})
    return day


def _parse_optional_int(raw):
    if raw in (None, ''):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


class PendingChangeViewSet(viewsets.ReadOnlyModelViewSet):
    """Checker queue: list/retrieve pending and completed proposals."""

    queryset = PendingChange.objects.all().select_related('made_by', 'checked_by')
    serializer_class = PendingChangeSerializer
    permission_classes = [IsAuthenticated]

    def _require_checker(self, request):
        from approvals.permissions import user_can_check
        from approvals.registry import ACTION_DEBT_COLLECTION, ACTION_SALE_COMPLETE

        if user_may_edit_financial_fields(request.user):
            return
        if user_can_check(request.user, ACTION_DEBT_COLLECTION) or user_can_check(
            request.user, ACTION_SALE_COMPLETE
        ):
            return
        raise PermissionDenied('Checker access required.')

    @staticmethod
    def _status_param(request):
        value = (request.query_params.get('status') or '').strip()
        if value == 'pending':
            return PendingChange.STATUS_PENDING
        return value

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self._status_param(self.request)
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
        if user_may_edit_financial_fields(request.user):
            return super().retrieve(request, *args, **kwargs)
        # Maker or checker who decided the row may open it for the accountability trail.
        change = (
            PendingChange.objects.filter(pk=kwargs.get('pk'))
            .filter(Q(made_by=request.user) | Q(checked_by=request.user))
            .first()
        )
        if not change:
            raise PermissionDenied('Submission not found.')
        return Response(PendingChangeSerializer(change).data)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """All rows awaiting checker action."""
        self._require_checker(request)
        qs = self.get_queryset().filter(status=PendingChange.STATUS_PENDING)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='pending-count')
    def pending_count(self, request):
        """
        Lightweight badge count — no per-row details serialization.

        Optional ``exclude_action_type`` (repeatable / comma-separated) drops
        sales-desk actions so Pending Approvals can exclude sale/debt queues.
        """
        self._require_checker(request)
        qs = PendingChange.objects.filter(status=PendingChange.STATUS_PENDING)
        action_type = request.query_params.get('action_type')
        if action_type:
            qs = qs.filter(action_type=action_type)
        raw_exclude = request.query_params.getlist('exclude_action_type')
        if not raw_exclude:
            csv = (request.query_params.get('exclude_action_type') or '').strip()
            if csv:
                raw_exclude = [p.strip() for p in csv.split(',') if p.strip()]
        if raw_exclude:
            qs = qs.exclude(action_type__in=raw_exclude)
        return Response({'count': qs.count()})

    @action(detail=False, methods=['get'], url_path='my-submissions')
    def my_submissions(self, request):
        """Submissions created by the current user (e.g. rejected past sales to fix)."""
        qs = self.get_queryset().filter(made_by=request.user)
        limit = min(int(request.query_params.get('limit', 20) or 20), 100)
        serializer = self.get_serializer(qs.order_by('-made_at')[:limit], many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='decision-people')
    def decision_people(self, request):
        """Distinct requesters and checkers for decision trail filters."""
        self._require_checker(request)
        decided = PendingChange.objects.exclude(
            status=PendingChange.STATUS_PENDING
        ).filter(checked_by__isnull=False)
        requesters = (
            decided.filter(made_by__isnull=False)
            .values('made_by_id', 'made_by__username')
            .distinct()
            .order_by('made_by__username')
        )
        checkers = (
            decided.values('checked_by_id', 'checked_by__username')
            .distinct()
            .order_by('checked_by__username')
        )
        return Response(
            {
                'requesters': [
                    {'id': row['made_by_id'], 'name': row['made_by__username']}
                    for row in requesters
                    if row['made_by_id']
                ],
                'checkers': [
                    {'id': row['checked_by_id'], 'name': row['checked_by__username']}
                    for row in checkers
                    if row['checked_by_id']
                ],
            }
        )

    @action(detail=False, methods=['get'], url_path='my-decisions')
    def my_decisions(self, request):
        """Decided rows — all checkers by default; filter by date and people."""
        self._require_checker(request)
        qs = (
            PendingChange.objects.exclude(status=PendingChange.STATUS_PENDING)
            .filter(checked_by__isnull=False)
            .select_related('made_by', 'checked_by')
            .order_by('-checked_at', '-id')
        )

        scope = (request.query_params.get('scope') or 'all').strip().lower()
        checked_by_id = _parse_optional_int(request.query_params.get('checked_by'))
        made_by_id = _parse_optional_int(request.query_params.get('made_by'))
        if checked_by_id is not None:
            qs = qs.filter(checked_by_id=checked_by_id)
        elif scope == 'mine':
            qs = qs.filter(checked_by=request.user)
        if made_by_id is not None:
            qs = qs.filter(made_by_id=made_by_id)

        day_from = _parse_query_date(
            request.query_params.get('date_from'), field_name='date_from'
        )
        day_to = _parse_query_date(
            request.query_params.get('date_to'), field_name='date_to'
        )
        if day_from is not None:
            qs = qs.filter(checked_at__date__gte=day_from)
        if day_to is not None:
            qs = qs.filter(checked_at__date__lte=day_to)

        status_filter = self._status_param(request)
        if status_filter:
            qs = qs.filter(status=status_filter)
        action_types = []
        for value in request.query_params.getlist('action_type'):
            if not value:
                continue
            action_types.extend(
                part.strip() for part in str(value).split(',') if part.strip()
            )
        if len(action_types) == 1:
            qs = qs.filter(action_type=action_types[0])
        elif len(action_types) > 1:
            qs = qs.filter(action_type__in=action_types)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
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

    @action(detail=True, methods=['post'])
    def resubmit(self, request, pk=None):
        change = self.get_object()
        body = ResubmitChangeSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            resubmit_change(
                change,
                request.user,
                reason=body.validated_data.get('reason') or '',
                request=request,
            )
        except DjangoValidationError as exc:
            if hasattr(exc, 'message_dict'):
                return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        change.refresh_from_db()
        return Response(PendingChangeSerializer(change).data)
