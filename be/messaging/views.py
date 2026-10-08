from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services


def _user_can(user, module: str, action: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    return profile.has_permission(module, action)


def _can_send_debt_reminders(user) -> bool:
    return _user_can(user, 'messaging', 'create') or _user_can(
        user, 'debt_management', 'update',
    )


def _can_view_debt_reminders(user) -> bool:
    return (
        _user_can(user, 'messaging', 'view')
        or _user_can(user, 'messaging', 'create')
        or _user_can(user, 'debt_management', 'view')
        or _user_can(user, 'debt_management', 'update')
    )


def _can_view_templates(user) -> bool:
    return _can_view_debt_reminders(user)


def _can_edit_templates(user) -> bool:
    return (
        _user_can(user, 'messaging', 'create')
        or _user_can(user, 'settings', 'manage')
        or _user_can(user, 'debt_management', 'update')
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sms_templates_list(request):
    if not _can_view_templates(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    return Response({'results': services.list_sms_templates()})


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def sms_template_detail(request, key: str):
    if not _can_view_templates(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        try:
            return Response(services.serialize_template(key))
        except services.MessagingError as exc:
            return Response(exc.detail, status=status.HTTP_404_NOT_FOUND)

    if not _can_edit_templates(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'DELETE' or request.data.get('reset'):
        try:
            return Response(services.reset_sms_template(key, user=request.user))
        except services.MessagingError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

    body = request.data.get('body')
    if body is None:
        return Response({'body': 'Required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        return Response(services.save_sms_template(key, str(body), user=request.user))
    except services.MessagingError as exc:
        return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def debt_reminders(request):
    """Legacy: send reminders one-by-one (limit 50). Prefer /reminders/debt/send/."""
    if not _can_send_debt_reminders(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    queued = services.queue_debt_reminders(created_by=request.user)
    return Response({
        'queued': len(queued),
        'ids': [m.id for m in queued],
    }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def debt_reminder_template(request):
    if not _can_view_debt_reminders(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        return Response(services.serialize_template('debt_reminder'))

    if not _can_send_debt_reminders(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    body = request.data.get('body')
    if body is None:
        return Response({'body': 'Required.'}, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        services.save_sms_template('debt_reminder', str(body), user=request.user)
    )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def debt_reminder_preview(request):
    """Generate the full debtor list with rendered SMS for verification."""
    if not _can_view_debt_reminders(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    template = None
    customer_ids = None
    if request.method == 'POST':
        template = request.data.get('template')
        raw_ids = request.data.get('customer_ids')
        if raw_ids is not None:
            try:
                customer_ids = [int(x) for x in raw_ids]
            except (TypeError, ValueError):
                return Response(
                    {'customer_ids': 'Must be a list of customer ids.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
    else:
        template = request.query_params.get('template')

    preview = services.build_debt_reminder_preview(
        template=template,
        customer_ids=customer_ids,
    )
    return Response(preview)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def debt_reminder_send(request):
    """Verify selection then send personalized bulk SMS (Mobile Sasa)."""
    if not _can_send_debt_reminders(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    template = request.data.get('template')
    save_template = bool(request.data.get('save_template', False))
    raw_ids = request.data.get('customer_ids')
    customer_ids = None
    if raw_ids is not None:
        try:
            customer_ids = [int(x) for x in raw_ids]
        except (TypeError, ValueError):
            return Response(
                {'customer_ids': 'Must be a list of customer ids.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not customer_ids:
            return Response(
                {'customer_ids': 'Select at least one debtor.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    result = services.send_debt_reminders(
        created_by=request.user,
        template=template,
        customer_ids=customer_ids,
        save_template=save_template,
    )
    return Response(result, status=status.HTTP_201_CREATED)


def _can_send_promos(user) -> bool:
    return _user_can(user, 'messaging', 'create') or _user_can(user, 'customers', 'update')


def _can_view_promos(user) -> bool:
    return (
        _user_can(user, 'messaging', 'view')
        or _user_can(user, 'messaging', 'create')
        or _user_can(user, 'customers', 'view')
        or _user_can(user, 'customers', 'update')
    )


def _parse_customer_ids(raw_ids):
    if raw_ids is None:
        return None, None
    try:
        customer_ids = [int(x) for x in raw_ids]
    except (TypeError, ValueError):
        return None, Response(
            {'customer_ids': 'Must be a list of customer ids.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return customer_ids, None


def _blast_request_args(request, *, require_ids_nonempty: bool = False):
    """Parse shared blast payload fields."""
    from messaging.template_catalog import get_spec

    data = request.data if request.method == 'POST' else request.query_params
    template_key = (data.get('template_key') or '').strip()
    if not template_key:
        return None, Response(
            {'template_key': 'Required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if get_spec(template_key) is None:
        return None, Response(
            {'template_key': f'Unknown template: {template_key}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    scope = (data.get('scope') or 'all').strip().lower()
    if scope not in ('all', 'one'):
        return None, Response(
            {'scope': 'Use "all" or "one".'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    customer_id = data.get('customer_id')
    if customer_id in ('', None):
        customer_id = None
    else:
        try:
            customer_id = int(customer_id)
        except (TypeError, ValueError):
            return None, Response(
                {'customer_id': 'Must be a customer id.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    customer_ids, err = _parse_customer_ids(data.get('customer_ids'))
    if err is not None:
        return None, err
    if require_ids_nonempty and customer_ids is not None and not customer_ids:
        return None, Response(
            {'customer_ids': 'Select at least one customer.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return {
        'template_key': template_key,
        'template': data.get('template'),
        'offer': data.get('offer'),
        'scope': scope,
        'customer_id': customer_id,
        'customer_ids': customer_ids,
        'save_template': bool(data.get('save_template', False)),
    }, None


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def customer_blast_preview(request):
    """Preview any SMS template for all (valid phones) or one customer."""
    if not _can_view_promos(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    from messaging.customer_blast import BlastError, build_customer_blast_preview

    if request.method == 'GET' and not (request.query_params.get('template_key') or '').strip():
        return Response(
            {'template_key': 'Required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    args, err = _blast_request_args(request)
    if err is not None:
        return err
    try:
        preview = build_customer_blast_preview(
            template_key=args['template_key'],
            template=args['template'],
            offer=args['offer'],
            scope=args['scope'],
            customer_id=args['customer_id'],
            customer_ids=args['customer_ids'],
        )
    except BlastError as exc:
        return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
    return Response(preview)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def customer_blast_send(request):
    """Send any SMS template to all valid phones or one customer."""
    if not _can_send_promos(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    from messaging.customer_blast import BlastError, send_customer_blast

    args, err = _blast_request_args(request, require_ids_nonempty=True)
    if err is not None:
        return err
    try:
        result = send_customer_blast(
            template_key=args['template_key'],
            created_by=request.user,
            template=args['template'],
            offer=args['offer'],
            scope=args['scope'],
            customer_id=args['customer_id'],
            customer_ids=args['customer_ids'],
            save_template=args['save_template'],
        )
    except BlastError as exc:
        return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def customer_week_preview(request):
    """Back-compat: Customer Week blast preview."""
    if not _can_view_promos(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    from messaging.customer_blast import BlastError, build_customer_blast_preview
    from messaging.models import SmsTemplate

    template = None
    offer = None
    customer_ids = None
    scope = 'all'
    customer_id = None
    if request.method == 'POST':
        template = request.data.get('template')
        offer = request.data.get('offer')
        scope = (request.data.get('scope') or 'all').strip().lower()
        raw_one = request.data.get('customer_id')
        if raw_one not in (None, ''):
            try:
                customer_id = int(raw_one)
            except (TypeError, ValueError):
                return Response(
                    {'customer_id': 'Must be a customer id.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        customer_ids, err = _parse_customer_ids(request.data.get('customer_ids'))
        if err is not None:
            return err
    else:
        template = request.query_params.get('template')
        offer = request.query_params.get('offer')

    try:
        preview = build_customer_blast_preview(
            template_key=SmsTemplate.KEY_CUSTOMER_WEEK,
            template=template,
            offer=offer,
            scope=scope,
            customer_id=customer_id,
            customer_ids=customer_ids,
        )
    except BlastError as exc:
        return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
    return Response(preview)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def customer_week_send(request):
    """Back-compat: Customer Week blast send."""
    if not _can_send_promos(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    from messaging.customer_blast import BlastError, send_customer_blast
    from messaging.models import SmsTemplate

    template = request.data.get('template')
    offer = request.data.get('offer')
    save_template = bool(request.data.get('save_template', False))
    scope = (request.data.get('scope') or 'all').strip().lower()
    raw_one = request.data.get('customer_id')
    customer_id = None
    if raw_one not in (None, ''):
        try:
            customer_id = int(raw_one)
        except (TypeError, ValueError):
            return Response(
                {'customer_id': 'Must be a customer id.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
    customer_ids, err = _parse_customer_ids(request.data.get('customer_ids'))
    if err is not None:
        return err
    if customer_ids is not None and not customer_ids:
        return Response(
            {'customer_ids': 'Select at least one customer.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        result = send_customer_blast(
            template_key=SmsTemplate.KEY_CUSTOMER_WEEK,
            created_by=request.user,
            template=template,
            offer=offer,
            scope=scope,
            customer_id=customer_id,
            customer_ids=customer_ids,
            save_template=save_template,
        )
    except BlastError as exc:
        return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
    return Response(result, status=status.HTTP_201_CREATED)
