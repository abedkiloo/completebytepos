from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import RequirePermPerAction

from .models import FieldOrder
from .order_serializers import (
    FieldOrderCreateSerializer,
    FieldOrderSerializer,
    FieldOrderSubmitSerializer,
)
from .order_services import FieldOrderTransitionError

FIELD_ORDER_PERMS = RequirePermPerAction(
    'agents',
    {
        'list': 'view',
        'retrieve': 'view',
        'create': 'create',
        'update': 'update',
        'partial_update': 'update',
        'destroy': 'update',
        'submit': 'update',
    },
)


class FieldOrderViewSet(viewsets.ModelViewSet):
    queryset = FieldOrder.objects.select_related(
        'site', 'customer', 'created_by', 'assigned_delivery_agent',
    ).prefetch_related('lines', 'site__media')
    serializer_class = FieldOrderSerializer
    permission_classes = [IsAuthenticated, FIELD_ORDER_PERMS]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        mine = self.request.query_params.get('mine')
        if mine in ('1', 'true', 'yes'):
            qs = qs.filter(created_by=self.request.user)
        return qs

    def create(self, request, *args, **kwargs):
        ser = FieldOrderCreateSerializer(
            data=request.data, context={'request': request},
        )
        ser.is_valid(raise_exception=True)
        order = ser.save()
        return Response(
            FieldOrderSerializer(order, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        order = self.get_object()
        ser = FieldOrderSubmitSerializer(
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
