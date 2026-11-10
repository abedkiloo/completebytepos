"""
Custom exception handler for DRF to add logging and ensure CORS headers.

Security: authenticated 403s are written to the append-only audit log
(web vs mobile channel included) so denied attempts cannot be disputed.
Audit write failures never change the HTTP response.
"""
import logging

from django.conf import settings
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    DRF exception hook: CORS on errors + non-blocking permission-denied audit.

    Args:
        exc: Raised exception.
        context: DRF context with ``request`` / ``view``.

    Returns:
        DRF ``Response`` or ``None`` when unhandled.
    """
    response = exception_handler(exc, context)

    if response is not None and response.status_code >= 500:
        logger.error(
            'DRF Exception: %s: %s',
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        logger.error('Response: %s - %s', response.status_code, response.data)

    if response is not None and response.status_code == 403:
        _audit_permission_denied(exc, context)

    if response is not None:
        request = context.get('request')
        if request:
            origin = request.META.get('HTTP_ORIGIN')
            if origin:
                if 'Access-Control-Allow-Origin' not in response:
                    if getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False):
                        response['Access-Control-Allow-Origin'] = origin
                    elif origin in getattr(settings, 'CORS_ALLOWED_ORIGINS', []):
                        response['Access-Control-Allow-Origin'] = origin

                if getattr(settings, 'CORS_ALLOW_CREDENTIALS', False):
                    if 'Access-Control-Allow-Credentials' not in response:
                        response['Access-Control-Allow-Credentials'] = 'true'

                if 'Access-Control-Allow-Methods' not in response:
                    methods = getattr(
                        settings,
                        'CORS_ALLOW_METHODS',
                        ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
                    )
                    response['Access-Control-Allow-Methods'] = ', '.join(methods)

                if 'Access-Control-Allow-Headers' not in response:
                    headers = getattr(settings, 'CORS_ALLOWED_HEADERS', [])
                    if isinstance(headers, list):
                        response['Access-Control-Allow-Headers'] = ', '.join(headers)

    return response


def _audit_permission_denied(exc, context) -> None:
    """
    Append a permission_denied audit row for authenticated denials.

    Never raises. Skips anonymous traffic to avoid noise from probes.
    """
    try:
        request = context.get('request')
        if request is None:
            return
        user = getattr(request, 'user', None)
        if user is None or not getattr(user, 'is_authenticated', False):
            return
        view = context.get('view')
        module = getattr(view, 'audit_module', None) or ''
        if not module:
            try:
                module = view.queryset.model._meta.app_label
            except Exception:
                module = ''
        if not isinstance(module, str):
            module = str(module or '')
        action = getattr(view, 'action', None) or getattr(request, 'method', '') or ''
        detail = ''
        try:
            detail = str(exc)[:200]
        except Exception:
            detail = type(exc).__name__
        from utils.audit_events import log_permission_denied

        log_permission_denied(
            request,
            module=(module or 'security')[:32],
            action=str(action)[:32],
            detail=detail,
        )
    except Exception:
        logger.exception('Failed to audit permission_denied')
