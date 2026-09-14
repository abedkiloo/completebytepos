from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import RequirePermPerAction
from agents.models import FieldOrder
from agents.order_serializers import (
    AssignOrderSerializer,
    FieldOrderSerializer,
    PackOrderSerializer,
)
from agents.order_services import FieldOrderTransitionError

DISPATCH_PERMS = RequirePermPerAction(
    'dispatch',
    {
        'list': 'view',
        'retrieve': 'view',
        'queue': 'view',
        'pack': 'update',
        'assign': 'update',
    },
)

QUEUE_STATUSES = (
    FieldOrder.STATUS_SUBMITTED,
    FieldOrder.STATUS_PACKING,
    FieldOrder.STATUS_READY,
)


class DispatchQueueViewSet(viewsets.ReadOnlyModelViewSet):
    """Dispatcher board: submitted / packing / ready orders."""

    serializer_class = FieldOrderSerializer
    permission_classes = [IsAuthenticated, DISPATCH_PERMS]
    queryset = FieldOrder.objects.select_related(
        'site', 'customer', 'created_by', 'assigned_delivery_agent',
    ).prefetch_related('lines', 'site__media')

    def get_queryset(self):
        qs = super().get_queryset().filter(status__in=QUEUE_STATUSES)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def _order(self, pk):
        return FieldOrder.objects.select_related(
            'site', 'customer', 'created_by', 'assigned_delivery_agent',
        ).prefetch_related('lines', 'site__media').get(pk=pk)

    @action(detail=False, methods=['get'], url_path='queue')
    def queue(self, request):
        ser = FieldOrderSerializer(
            self.get_queryset(), many=True, context={'request': request},
        )
        return Response(ser.data)

    @action(detail=True, methods=['post'], url_path='pack')
    def pack(self, request, pk=None):
        try:
            order = self._order(pk)
        except FieldOrder.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        ser = PackOrderSerializer(
            data=request.data or {},
            context={'order': order, 'request': request},
        )
        try:
            ser.is_valid(raise_exception=True)
            order = ser.save()
        except FieldOrderTransitionError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            FieldOrderSerializer(order, context={'request': request}).data,
        )

    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, pk=None):
        try:
            order = self._order(pk)
        except FieldOrder.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        ser = AssignOrderSerializer(
            data=request.data,
            context={'order': order, 'request': request},
        )
        try:
            ser.is_valid(raise_exception=True)
            order = ser.save()
        except FieldOrderTransitionError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            FieldOrderSerializer(order, context={'request': request}).data,
        )
