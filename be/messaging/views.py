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
