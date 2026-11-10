from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import RequirePerm, RequirePermPerAction

from .models import PaymentIntent
from .serializers import (
    CreateIntentSerializer,
    PaymentIntentSerializer,
    PublicInvoiceSerializer,
)
from . import services
from .services import PaymentTransitionError

PAYMENTS_PERMS = RequirePermPerAction(
    'payments',
    {
        'list': 'view',
        'retrieve': 'view',
        'create': 'create',
        'stk': 'create',
        'query': 'view',
    },
)


class PaymentIntentViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, PAYMENTS_PERMS]
    serializer_class = PaymentIntentSerializer
    queryset = PaymentIntent.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(created_by=user)

    def create(self, request):
        ser = CreateIntentSerializer(data=request.data, context={'request': request})
        try:
            ser.is_valid(raise_exception=True)
            intent = ser.save()
        except PaymentTransitionError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            PaymentIntentSerializer(intent).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, pk=None):
        intent = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(PaymentIntentSerializer(intent).data)

    @action(detail=True, methods=['post'], url_path='stk')
    def stk(self, request, pk=None):
        intent = get_object_or_404(self.get_queryset(), pk=pk)
        try:
            intent = services.initiate_stk(intent)
        except PaymentTransitionError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(PaymentIntentSerializer(intent).data)

    @action(detail=True, methods=['post'], url_path='query')
    def query(self, request, pk=None):
        intent = get_object_or_404(self.get_queryset(), pk=pk)
        try:
            intent = services.reconcile_query(intent)
        except PaymentTransitionError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(PaymentIntentSerializer(intent).data)


@api_view(['POST'])
@permission_classes([AllowAny])
def daraja_callback(request):
    """
    Daraja STK callback — no JWT.

    Hardening (when configured):
      * ``DARAJA_CALLBACK_SECRET`` must match header ``X-Callback-Secret``
        or body ``callback_secret``.
      * ``DARAJA_CALLBACK_IPS`` optional IP allowlist.
      * Paid callbacks must report an Amount matching the intent.
    """
    from django.conf import settings as django_settings

    expected = (getattr(django_settings, 'DARAJA_CALLBACK_SECRET', '') or '').strip()
    if expected:
        import hmac

        provided = (
            (request.headers.get('X-Callback-Secret') if hasattr(request, 'headers') else None)
            or request.META.get('HTTP_X_CALLBACK_SECRET')
            or (request.data.get('callback_secret') if hasattr(request, 'data') else None)
            or ''
        )
        provided = str(provided).strip()
        if not provided or not hmac.compare_digest(
            provided.encode('utf-8'), expected.encode('utf-8'),
        ):
            return Response(
                {'callback': 'Invalid callback secret.'},
                status=status.HTTP_403_FORBIDDEN,
            )

    allowed_ips = getattr(django_settings, 'DARAJA_CALLBACK_IPS', None) or []
    if allowed_ips:
        remote = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR')
            or ''
        )
        if remote not in allowed_ips:
            return Response(
                {'callback': 'Callback source not allowed.'},
                status=status.HTTP_403_FORBIDDEN,
            )

    try:
        intent = services.process_callback(request.data if isinstance(request.data, dict) else {})
    except PaymentTransitionError as exc:
        return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
    return Response({
        'ResultCode': 0,
        'ResultDesc': 'Accepted',
        'intent_id': intent.id if intent else None,
        'status': intent.status if intent else None,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def public_invoice(request, token):
    intent = get_object_or_404(PaymentIntent, public_token=token)
    data = PublicInvoiceSerializer(intent).data
    from payments.config import get_brand_blurb
    data['brand_blurb'] = get_brand_blurb()
    return Response(data)
