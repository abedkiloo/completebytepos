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


def _debt_reminder_customer_ids(user, customer_ids: list[int] | None):
    """
    Restrict debt-reminder recipients to customers the user may see.

    Args:
        user: Authenticated request user.
        customer_ids: Optional explicit subset; None means “all visible debtors”.

    Returns:
        Filtered id list, or None when unrestricted (store-wide visibility).
    """
    from sales.models import Customer
    from sales.visibility import apply_customer_visibility, user_limited_to_own_customers

    if not user_limited_to_own_customers(user):
        if customer_ids is None:
            return None
        visible = set(
            apply_customer_visibility(
                Customer.objects.filter(pk__in=customer_ids), user,
            ).values_list('pk', flat=True)
        )
        return [cid for cid in customer_ids if cid in visible]

    qs = apply_customer_visibility(Customer.objects.all(), user)
    if customer_ids is not None:
        qs = qs.filter(pk__in=customer_ids)
    return list(qs.values_list('pk', flat=True))


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
            payload = services.reset_sms_template(key, user=request.user)
        except services.MessagingError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        try:
            from utils.audit_events import log_simple_action

            log_simple_action(
                request,
                'sms_template_reset',
                None,
                module='messaging',
                changes={'key': key},
                object_repr=f'SMS template {key}',
            )
        except Exception:
            pass
        return Response(payload)

    body = request.data.get('body')
    if body is None:
        return Response({'body': 'Required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        payload = services.save_sms_template(key, str(body), user=request.user)
    except services.MessagingError as exc:
        return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
    try:
        from utils.audit_events import log_simple_action

        log_simple_action(
            request,
            'sms_template_update',
            None,
            module='messaging',
            changes={'key': key},
            object_repr=f'SMS template {key}',
        )
    except Exception:
        pass
    return Response(payload)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def debt_reminders(request):
    """Legacy: send reminders one-by-one (limit 50). Prefer /reminders/debt/send/."""
    if not _can_send_debt_reminders(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    queued = services.queue_debt_reminders(created_by=request.user)
    try:
        from utils.audit_events import log_simple_action

        log_simple_action(
            request,
            'sms_debt_reminders_queue',
            None,
            module='messaging',
            changes={'queued': len(queued)},
            object_repr='Debt reminders queued',
        )
    except Exception:
        pass
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
        customer_ids=_debt_reminder_customer_ids(request.user, customer_ids),
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
        customer_ids=_debt_reminder_customer_ids(request.user, customer_ids),
        save_template=save_template,
    )
    try:
        from utils.audit_events import log_simple_action

        log_simple_action(
            request,
            'sms_debt_reminders_send',
            None,
            module='messaging',
            changes={
                'selected': len(customer_ids or []),
                'save_template': save_template,
                'result_keys': sorted(list(result.keys())) if isinstance(result, dict) else [],
            },
            object_repr='Debt reminders sent',
        )
    except Exception:
        pass
    return Response(result, status=status.HTTP_201_CREATED)


def _can_send_promos(user) -> bool:
    # Sending requires messaging.create — customers.update alone was enough
    # to blast every phone (cost + phishing). View stays broader.
    return _user_can(user, 'messaging', 'create')


def _can_view_promos(user) -> bool:
    return (
        _user_can(user, 'messaging', 'view')
        or _user_can(user, 'messaging', 'create')
        or _user_can(user, 'customers', 'view')
        or _user_can(user, 'customers', 'update')
    )


def _can_blast_all_customers(user) -> bool:
    """
    Store-wide SMS blast requires messaging.create (not customers.update).

    Rate limits on send endpoints further cap cost abuse.
    """
    return _can_send_promos(user)


def _visible_customer_or_404(user, customer_id: int):
    """Return customer if visible to user; else a 404 Response."""
    from sales.models import Customer
    from sales.visibility import apply_customer_visibility

    qs = apply_customer_visibility(Customer.objects.all(), user)
    customer = qs.filter(pk=customer_id).first()
    if customer is None:
        return None, Response(
            {'customer_id': 'Customer not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    return customer, None


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

    if scope == 'all' and not _can_blast_all_customers(request.user):
        return None, Response(
            {'scope': 'Only managers and admins can message all customers.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if customer_id is not None:
        _customer, cerr = _visible_customer_or_404(request.user, customer_id)
        if cerr is not None:
            return None, cerr

    if customer_ids is not None:
        from sales.models import Customer
        from sales.visibility import apply_customer_visibility

        visible = set(
            apply_customer_visibility(Customer.objects.filter(pk__in=customer_ids), request.user)
            .values_list('pk', flat=True)
        )
        missing = [cid for cid in customer_ids if cid not in visible]
        if missing:
            return None, Response(
                {'customer_ids': 'One or more customers were not found.'},
                status=status.HTTP_404_NOT_FOUND,
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

    from accounts.throttles import SmsBlastRateThrottle
    from messaging.customer_blast import BlastError, send_customer_blast

    throttle = SmsBlastRateThrottle()
    if not throttle.allow_request(request, customer_blast_send):
        return Response(
            {'detail': 'SMS blast rate limit exceeded. Try again later.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

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


def _week_blast_scope_args(request, *, require_ids_nonempty: bool = False):
    """
    Parse Customer Week payload and apply the same blast security gates.

    Args:
        request: Authenticated DRF request.
        require_ids_nonempty: When True, empty ``customer_ids`` is rejected.

    Returns:
        ``(args_dict, None)`` or ``(None, Response)`` on validation / auth errors.
    """
    from messaging.models import SmsTemplate

    data = request.data if request.method == 'POST' else request.query_params
    scope = (data.get('scope') or 'all').strip().lower()
    if scope not in ('all', 'one'):
        return None, Response(
            {'scope': 'Use "all" or "one".'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if scope == 'all' and not _can_blast_all_customers(request.user):
        return None, Response(
            {'scope': 'Only managers and admins can message all customers.'},
            status=status.HTTP_403_FORBIDDEN,
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
    if customer_id is not None:
        _customer, cerr = _visible_customer_or_404(request.user, customer_id)
        if cerr is not None:
            return None, cerr

    customer_ids, err = _parse_customer_ids(data.get('customer_ids'))
    if err is not None:
        return None, err
    if require_ids_nonempty and customer_ids is not None and not customer_ids:
        return None, Response(
            {'customer_ids': 'Select at least one customer.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if customer_ids is not None:
        from sales.models import Customer
        from sales.visibility import apply_customer_visibility

        visible = set(
            apply_customer_visibility(
                Customer.objects.filter(pk__in=customer_ids), request.user,
            ).values_list('pk', flat=True)
        )
        if any(cid not in visible for cid in customer_ids):
            return None, Response(
                {'customer_ids': 'One or more customers were not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

    return {
        'template_key': SmsTemplate.KEY_CUSTOMER_WEEK,
        'template': data.get('template'),
        'offer': data.get('offer'),
        'scope': scope,
        'customer_id': customer_id,
        'customer_ids': customer_ids,
        'save_template': bool(data.get('save_template', False)) if request.method == 'POST' else False,
    }, None


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def customer_week_preview(request):
    """Back-compat: Customer Week blast preview."""
    if not _can_view_promos(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    from messaging.customer_blast import BlastError, build_customer_blast_preview

    args, err = _week_blast_scope_args(request)
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
def customer_week_send(request):
    """Back-compat: Customer Week blast send."""
    if not _can_send_promos(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    from accounts.throttles import SmsBlastRateThrottle
    from messaging.customer_blast import BlastError, send_customer_blast

    throttle = SmsBlastRateThrottle()
    if not throttle.allow_request(request, customer_week_send):
        return Response(
            {'detail': 'SMS blast rate limit exceeded. Try again later.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    args, err = _week_blast_scope_args(request, require_ids_nonempty=True)
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
