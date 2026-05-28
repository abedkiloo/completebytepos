"""
Lightweight helpers for writing to the ``accounts.AuditLog`` append-only log.

The goal is to make logging from anywhere in the codebase a one-liner:

    from utils.audit import log_audit
    log_audit(request, AuditLog.ACTION_UPDATE, instance, before=before, after=after)

The helpers degrade safely — if anything goes wrong during logging (DB down,
missing field, serialisation error), they swallow the exception and log a
warning rather than failing the user's request. Audit logging is a *safety
net*, not the source of truth, so it must never block a successful API call.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models import Model
from django.forms.models import model_to_dict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def log_audit(
    request,
    action: str,
    instance: Model | None = None,
    *,
    module: str = '',
    changes: dict | None = None,
    object_repr: str | None = None,
):
    """
    Write one row to ``AuditLog``.

    Args:
        request: the DRF/Django request; used to extract user, IP, path, UA.
            May be None for system events (e.g. background jobs).
        action: short verb. Prefer one of ``AuditLog.ACTION_*`` constants but
            free strings are allowed for domain-specific events.
        instance: optional model instance the event relates to. We record
            ``app_label.ModelName`` and the PK.
        module: optional override of the permission module string
            (``'sales'``, ``'products'``, ...). Defaults to the instance's
            ``app_label`` if not supplied.
        changes: optional JSON-serializable dict to attach (e.g. a diff
            produced by ``diff_instance`` below, or a custom event payload).
        object_repr: optional pretty-printable string. Defaults to
            ``str(instance)`` if instance is given.
    """

    # Hard-coded import-deferral so this module is import-time safe even
    # before Django finishes setting up the app registry.
    from accounts.models import AuditLog

    try:
        user = None
        username = ''
        ip = None
        ua = ''
        path = ''
        method = ''

        if request is not None:
            req_user = getattr(request, 'user', None)
            if req_user is not None and getattr(req_user, 'is_authenticated', False):
                user = req_user
                username = getattr(req_user, 'username', '') or ''
            ip = _client_ip(request)
            ua = (request.META.get('HTTP_USER_AGENT') or '')[:255]
            path = (getattr(request, 'path', '') or '')[:255]
            method = getattr(request, 'method', '') or ''

        object_type = ''
        object_id = ''
        if instance is not None:
            meta = instance._meta
            object_type = f"{meta.app_label}.{meta.object_name}"
            pk = getattr(instance, 'pk', None)
            object_id = '' if pk is None else str(pk)[:64]
            if not module:
                module = meta.app_label
            if object_repr is None:
                try:
                    object_repr = str(instance)[:255]
                except Exception:
                    object_repr = f"<{object_type}#{object_id}>"

        AuditLog.objects.create(
            user=user,
            username_snapshot=username[:150],
            action=action[:32],
            module=(module or '')[:32],
            object_type=object_type[:64],
            object_id=object_id,
            object_repr=(object_repr or '')[:255],
            changes=changes or {},
            ip_address=ip,
            user_agent=ua,
            path=path,
            method=method[:8],
        )
    except Exception:  # pragma: no cover - audit must never break the request
        logger.exception("Failed to write audit log for action=%s", action)


def diff_instance(before: Model | None, after: Model | None) -> dict:
    """
    Return a JSON-serializable ``{field: {'from': X, 'to': Y}}`` map of the
    differences between two snapshots of the same model instance.

    ``before`` may be ``None`` (creation) or ``after`` may be ``None``
    (deletion). FKs are recorded as their PK (Django's ``model_to_dict``
    handles this). DateTime / Decimal / UUID values are stringified so the
    JSONField round-trips cleanly.
    """
    def _normalize(d: dict) -> dict:
        return {k: _json_safe(v) for k, v in d.items()}

    if before is None and after is None:
        return {}
    if before is None:
        return {'__created__': _normalize(model_to_dict(after))}
    if after is None:
        return {'__deleted__': _normalize(model_to_dict(before))}

    before_d = _normalize(model_to_dict(before))
    after_d = _normalize(model_to_dict(after))
    diff: dict = {}
    for k in before_d.keys() | after_d.keys():
        b = before_d.get(k)
        a = after_d.get(k)
        if b != a:
            diff[k] = {'from': b, 'to': a}
    return diff


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _client_ip(request) -> str | None:
    """Best-effort client IP extraction; honours X-Forwarded-For first hop."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        # First IP in the list is the originating client.
        ip = forwarded.split(',')[0].strip()
        if ip:
            return ip
    return request.META.get('REMOTE_ADDR') or None


def _json_safe(value: Any) -> Any:
    """Convert non-JSON-native values into JSON-serializable representations."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return str(value)
