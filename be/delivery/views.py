from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import RequirePerm, RequirePermPerAction
from agents.models import FieldOrder
from agents.order_serializers import FieldOrderSerializer
from agents.order_services import FieldOrderTransitionError, claim_ready_order

from .config import ALLOW_OFFLINE_POD_QUEUE, REQUIRE_POD_TO_COMPLETE
from .models import DeliveryStop
from .serializers import (
    CollectSerializer,
    DeliveryRouteSerializer,
    DeliveryStopSerializer,
    LinesUpdateSerializer,
    PodSerializer,
    ProposePinSerializer,
    ProofOfDeliverySerializer,
)
from . import services
from .services import DeliveryTransitionError

DELIVERY_VIEW = RequirePerm('delivery', 'view')
DELIVERY_UPDATE = RequirePerm('delivery', 'update')
DELIVERY_PERMS = RequirePermPerAction(
    'delivery',
    {
        'list': 'view',
        'retrieve': 'view',
        'arrive': 'update',
        'start': 'update',
        'lines': 'update',
        'collect': 'update',
        'pod': 'update',
        'complete': 'update',
        'propose_pin': 'update',
    },
)


def _stop_qs():
    return DeliveryStop.objects.select_related(
        'route', 'field_order', 'field_order__site', 'field_order__customer',
        'pod',
    ).prefetch_related(
        'line_results', 'field_order__site__media', 'line_results__product',
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, DELIVERY_VIEW])
def today_route(request):
    route = services.ensure_today_route(request.user)
    route = (
        type(route).objects.prefetch_related(
            'stops__line_results',
            'stops__field_order__site__media',
            'stops__field_order__customer',
            'stops__pod',
        ).get(pk=route.pk)
    )
    return Response(
        DeliveryRouteSerializer(route, context={'request': request}).data,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, DELIVERY_VIEW])
def delivery_config(request):
    return Response({
        'require_pod_to_complete': REQUIRE_POD_TO_COMPLETE,
        'allow_offline_pod_queue': ALLOW_OFFLINE_POD_QUEUE,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, DELIVERY_VIEW])
def available_orders(request):
    """Ready, unassigned field orders drivers may claim (after assigned work)."""
    qs = (
        FieldOrder.objects.filter(
            status=FieldOrder.STATUS_READY,
            assigned_delivery_agent__isnull=True,
        )
        .select_related('site', 'customer', 'created_by', 'assigned_delivery_agent')
        .prefetch_related('lines', 'lines__variant', 'site__media')
        .order_by('packed_at', 'id')
    )
    return Response(
        FieldOrderSerializer(qs, many=True, context={'request': request}).data,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, DELIVERY_UPDATE])
def claim_order(request, pk):
    """
    Self-assign a ready unassigned order onto the caller's today route.

    Rejects if dispatch already assigned someone — assign takes priority.
    """
    order = get_object_or_404(
        FieldOrder.objects.select_related(
            'site', 'customer', 'created_by', 'assigned_delivery_agent',
        ).prefetch_related('lines', 'lines__variant', 'site__media'),
        pk=pk,
    )
    try:
        order = claim_ready_order(order, request.user)
    except FieldOrderTransitionError as exc:
        return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        FieldOrderSerializer(order, context={'request': request}).data,
    )

class DeliveryStopViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DeliveryStopSerializer
    permission_classes = [IsAuthenticated, DELIVERY_PERMS]

    def get_queryset(self):
        qs = _stop_qs()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(route__delivery_agent=user)

    def _reload(self, pk):
        return get_object_or_404(self.get_queryset(), pk=pk)

    @action(detail=True, methods=['post'], url_path='arrive')
    def arrive(self, request, pk=None):
        stop = self._reload(pk)
        try:
            services.arrive(stop)
        except DeliveryTransitionError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DeliveryStopSerializer(self._reload(pk), context={'request': request}).data,
        )

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        stop = self._reload(pk)
        try:
            services.start_delivery(stop)
        except DeliveryTransitionError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DeliveryStopSerializer(self._reload(pk), context={'request': request}).data,
        )

    @action(detail=True, methods=['post'], url_path='lines')
    def lines(self, request, pk=None):
        stop = self._reload(pk)
        ser = LinesUpdateSerializer(
            data=request.data,
            context={'stop': stop, 'request': request},
        )
        try:
            ser.is_valid(raise_exception=True)
            ser.save()
        except DeliveryTransitionError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DeliveryStopSerializer(self._reload(pk), context={'request': request}).data,
        )

    @action(detail=True, methods=['post'], url_path='collect')
    def collect(self, request, pk=None):
        stop = self._reload(pk)
        ser = CollectSerializer(
            data=request.data,
            context={'stop': stop, 'request': request},
        )
        try:
            ser.is_valid(raise_exception=True)
            ser.save()
        except DeliveryTransitionError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DeliveryStopSerializer(self._reload(pk), context={'request': request}).data,
        )

    @action(detail=True, methods=['post'], url_path='pod')
    def pod(self, request, pk=None):
        stop = self._reload(pk)
        ser = PodSerializer(
            data=request.data,
            context={'stop': stop, 'request': request},
        )
        try:
            ser.is_valid(raise_exception=True)
            pod = ser.save()
        except DeliveryTransitionError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ProofOfDeliverySerializer(pod, context={'request': request}).data,
        )

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        stop = self._reload(pk)
        try:
            services.complete_stop(stop)
        except DeliveryTransitionError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DeliveryStopSerializer(self._reload(pk), context={'request': request}).data,
        )

    @action(detail=True, methods=['post'], url_path='propose-pin')
    def propose_pin(self, request, pk=None):
        stop = self._reload(pk)
        ser = ProposePinSerializer(
            data=request.data,
            context={'stop': stop, 'request': request},
        )
        ser.is_valid(raise_exception=True)
        corr = ser.save()
        return Response({
            'id': corr.id,
            'status': corr.status,
            'latitude': str(corr.latitude),
            'longitude': str(corr.longitude),
        }, status=status.HTTP_201_CREATED)
