from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import RequirePerm, RequirePermPerAction
from agents.models import FieldOrder
from agents.order_serializers import FieldOrderSerializer
from agents.order_services import FieldOrderTransitionError, claim_ready_order

from .config import ALLOW_OFFLINE_POD_QUEUE, REQUIRE_POD_TO_COMPLETE
from .maps import (
    build_route_geometry,
    empty_geometry,
    maps_public_config,
    user_may_view_agent_route,
)
from .models import DeliveryRoute, DeliveryStop
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
        'maps': maps_public_config(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, DELIVERY_VIEW])
def today_route_geometry(request):
    route = services.ensure_today_route(request.user)
    return Response(build_route_geometry(route, request=request))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_route_geometry(request):
    raw_agent = request.query_params.get('agent_id')
    if not raw_agent:
        return Response({'detail': 'agent_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        agent_id = int(raw_agent)
    except (TypeError, ValueError):
        return Response(
            {'detail': 'agent_id must be an integer.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not user_may_view_agent_route(request.user, agent_id):
        return Response(
            {'detail': 'You cannot view this driver’s route.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    date_raw = request.query_params.get('date')
    if date_raw:
        route_date = parse_date(date_raw)
        if route_date is None:
            return Response({'detail': 'Invalid date.'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        route_date = timezone.localdate()
    route = DeliveryRoute.objects.filter(
        delivery_agent_id=agent_id,
        route_date=route_date,
    ).select_related('delivery_agent').first()
    if route is None:
        agent = User.objects.filter(pk=agent_id).first()
        return Response(empty_geometry(agent_id, route_date, request=request, agent=agent))
    return Response(build_route_geometry(route, request=request))


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
