from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import RequirePermPerAction
from accounts.role_definitions import ROLE_DELIVERY_AGENT
from agents.models import FieldOrder
from agents.order_serializers import (
    AssignOrderSerializer,
    FieldOrderSerializer,
    PackOrderSerializer,
)
from agents.order_services import FieldOrderTransitionError
from django.contrib.auth.models import User

from .driver_create import CreateDriverSerializer, driver_payload

DISPATCH_PERMS = RequirePermPerAction(
    'dispatch',
    {
        'list': 'view',
        'retrieve': 'view',
        'queue': 'view',
        'drivers': 'view',
        'create_driver': 'update',
        'pack': 'update',
        'assign': 'update',
    },
)

QUEUE_STATUSES = (
    FieldOrder.STATUS_SUBMITTED,
    FieldOrder.STATUS_PACKING,
    FieldOrder.STATUS_READY,
)


def _apply_field_order_filters(qs, params):
    """Shared date / status / customer filters for admin + queue."""
    status_filter = params.get('status')
    if status_filter:
        # Convenience buckets for the admin Field Sales UI.
        if status_filter == 'awaiting_pack':
            qs = qs.filter(
                status__in=(
                    FieldOrder.STATUS_SUBMITTED,
                    FieldOrder.STATUS_PACKING,
                ),
            )
        elif status_filter == 'dispatched':
            qs = qs.filter(
                status__in=(
                    FieldOrder.STATUS_OUT_FOR_DELIVERY,
                    FieldOrder.STATUS_DONE,
                ),
            )
        else:
            qs = qs.filter(status=status_filter)

    date_from = params.get('date_from')
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    date_to = params.get('date_to')
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    search = (params.get('search') or '').strip()
    if search:
        from django.db.models import Q

        q = (
            Q(customer__name__icontains=search)
            | Q(customer__phone__icontains=search)
            | Q(site__label__icontains=search)
            | Q(notes__icontains=search)
        )
        if search.isdigit():
            q = q | Q(pk=int(search))
        qs = qs.filter(q)
    return qs


class DispatchQueueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Dispatcher / admin board for field (visit) orders.

    - list: all field orders with date/status/customer filters
    - queue: submitted/packing/ready only (mobile pack board)
    - pack: mark ready for pickup
    - assign: hand to delivery driver
    """

    serializer_class = FieldOrderSerializer
    permission_classes = [IsAuthenticated, DISPATCH_PERMS]
    queryset = FieldOrder.objects.select_related(
        'site', 'customer', 'created_by', 'assigned_delivery_agent',
    ).prefetch_related('lines', 'lines__variant', 'site__media')

    def get_queryset(self):
        qs = super().get_queryset()
        return _apply_field_order_filters(qs, self.request.query_params)

    def _order(self, pk):
        return FieldOrder.objects.select_related(
            'site', 'customer', 'created_by', 'assigned_delivery_agent',
        ).prefetch_related('lines', 'lines__variant', 'site__media').get(pk=pk)

    def _driver_queryset(self):
        return (
            User.objects.filter(
                is_active=True,
                profile__custom_role__name=ROLE_DELIVERY_AGENT,
                profile__is_active=True,
            )
            .select_related('profile')
            .order_by('first_name', 'last_name', 'username')
        )

    @action(detail=False, methods=['get'], url_path='drivers')
    def drivers(self, request):
        """Active users with the Delivery Driver role for assign pickers."""
        return Response([driver_payload(u) for u in self._driver_queryset()])

    @action(detail=False, methods=['post'], url_path='create-driver')
    def create_driver(self, request):
        """Add a Delivery Driver so field orders can be assigned immediately."""
        ser = CreateDriverSerializer(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        user = ser.save()
        return Response(
            driver_payload(user, temporary_password=user._temporary_password),
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], url_path='queue')
    def queue(self, request):
        qs = self.get_queryset().filter(status__in=QUEUE_STATUSES)
        ser = FieldOrderSerializer(
            qs, many=True, context={'request': request},
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
