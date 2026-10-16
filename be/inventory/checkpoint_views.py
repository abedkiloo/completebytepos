from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import RequirePermPerAction
from inventory.checkpoint_serializers import (
    CountCheckpointLineSerializer,
    OpenCheckpointSerializer,
    StockCheckpointLineSerializer,
    StockCheckpointListSerializer,
    StockCheckpointSerializer,
)
from inventory.checkpoint_services import (
    blocked_product_ids,
    cancel_checkpoint,
    close_checkpoint,
    count_checkpoint_line,
    latest_closed_checkpoint,
    open_checkpoint,
)
from inventory.models import StockCheckpoint, StockCheckpointLine
from settings.utils import get_current_branch
from utils.audit_mixin import AuditedModelViewSetMixin

CHECKPOINT_PERMS = RequirePermPerAction(
    'inventory',
    {
        'list': 'manage',
        'retrieve': 'manage',
        'create': 'manage',
        'open': 'manage',
        'count_line': 'manage',
        'close': 'manage',
        'cancel': 'manage',
        'baselines': 'view',
        'blocked_products': 'view',
    },
)


class StockCheckpointViewSet(AuditedModelViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Admin stock checkpoints: open → count lines → close (report baseline)."""

    permission_classes = [IsAuthenticated, CHECKPOINT_PERMS]
    audit_module = 'inventory'
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        return (
            StockCheckpoint.objects.all()
            .select_related('opened_by', 'closed_by')
            .annotate(
                pending_line_count=Count(
                    'lines',
                    filter=Q(lines__status=StockCheckpointLine.STATUS_PENDING),
                ),
                counted_line_count=Count(
                    'lines',
                    filter=Q(lines__status=StockCheckpointLine.STATUS_COUNTED),
                ),
                _line_count=Count('lines'),
            )
            .order_by('-opened_at')
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return StockCheckpointListSerializer
        return StockCheckpointSerializer

    def retrieve(self, request, *args, **kwargs):
        checkpoint = self.get_object()
        # Prefetch lines for detail
        checkpoint = (
            StockCheckpoint.objects.filter(pk=checkpoint.pk)
            .select_related('opened_by', 'closed_by')
            .prefetch_related(
                'lines__product',
                'lines__variant',
                'lines__variant__size',
                'lines__variant__color',
                'lines__counted_by',
                'lines__movement',
            )
            .first()
        )
        return Response(StockCheckpointSerializer(checkpoint).data)

    @action(detail=False, methods=['post'], url_path='open')
    def open(self, request):
        ser = OpenCheckpointSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            checkpoint = open_checkpoint(
                title=data['title'],
                user=request.user,
                product_ids=data.get('product_ids') or [],
                include_all_tracked=bool(data.get('include_all_tracked')),
                notes=data.get('notes') or '',
            )
        except ValidationError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        detail = (
            StockCheckpoint.objects.filter(pk=checkpoint.pk)
            .prefetch_related('lines__product', 'lines__variant')
            .first()
        )
        return Response(
            StockCheckpointSerializer(detail).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path=r'lines/(?P<line_id>[0-9]+)/count',
    )
    def count_line(self, request, pk=None, line_id=None):
        ser = CountCheckpointLineSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            line = count_checkpoint_line(
                line_id=int(line_id),
                counted_qty=ser.validated_data['counted_qty'],
                user=request.user,
                branch=get_current_branch(request),
            )
        except ValidationError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # Ensure line belongs to this checkpoint
        if str(line.checkpoint_id) != str(pk):
            return Response(
                {'error': 'Line does not belong to this checkpoint.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(StockCheckpointLineSerializer(line).data)

    @action(detail=True, methods=['post'], url_path='close')
    def close(self, request, pk=None):
        try:
            checkpoint = close_checkpoint(checkpoint_id=int(pk), user=request.user)
        except ValidationError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(StockCheckpointListSerializer(checkpoint).data)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        try:
            checkpoint = cancel_checkpoint(checkpoint_id=int(pk), user=request.user)
        except ValidationError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(StockCheckpointListSerializer(checkpoint).data)

    @action(
        detail=False,
        methods=['get'],
        url_path='baselines',
        permission_classes=[IsAuthenticated],
    )
    def baselines(self, request):
        """Closed checkpoints for report markers / since filters."""
        qs = (
            StockCheckpoint.objects.filter(status=StockCheckpoint.STATUS_CLOSED)
            .select_related('opened_by', 'closed_by')
            .annotate(
                pending_line_count=Count(
                    'lines',
                    filter=Q(lines__status=StockCheckpointLine.STATUS_PENDING),
                ),
                counted_line_count=Count(
                    'lines',
                    filter=Q(lines__status=StockCheckpointLine.STATUS_COUNTED),
                ),
                _line_count=Count('lines'),
            )
            .order_by('-closed_at')
        )
        latest = latest_closed_checkpoint()
        return Response(
            {
                'latest_closed_id': latest.id if latest else None,
                'latest_closed_at': latest.closed_at if latest else None,
                'results': StockCheckpointListSerializer(qs[:50], many=True).data,
            }
        )

    @action(
        detail=False,
        methods=['get'],
        url_path='blocked-products',
        permission_classes=[IsAuthenticated],
    )
    def blocked_products(self, request):
        """Product ids currently blocked from sale (pending open-checkpoint lines)."""
        return Response({'product_ids': sorted(blocked_product_ids())})
