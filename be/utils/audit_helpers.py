"""
Central audit writers for DRF viewsets and custom @action endpoints.

Every state-changing API should call one of:
  - ``audited_perform_create`` / ``audited_perform_update`` / ``audited_perform_destroy``
  - ``log_domain_event`` for service-layer or @action flows
"""

from __future__ import annotations

from typing import Any

from django.db.models import Model
from rest_framework import serializers

from utils.audit import diff_instance, log_audit


def _module_for(view, instance: Model | None) -> str:
    if getattr(view, 'audit_module', None):
        return view.audit_module
    if instance is not None:
        return instance._meta.app_label
    return ''


def _snapshot(instance: Model | None) -> dict:
    if instance is None:
        return {}
    try:
        from django.forms.models import model_to_dict
        from utils.audit import _json_safe

        snap = model_to_dict(instance)
        snap['__str__'] = str(instance)[:255]
        return {k: _json_safe(v) for k, v in snap.items()}
    except Exception:
        return {}


def _diff_snapshots(before: dict, after_instance: Model) -> dict:
    after = _snapshot(after_instance)
    diff: dict = {}
    for key in before.keys() | after.keys():
        if key.startswith('__'):
            continue
        if before.get(key) != after.get(key):
            diff[key] = {'from': before.get(key), 'to': after.get(key)}
    return diff


def audited_perform_create(view, serializer, **save_kwargs) -> Model:
    """
    Save via serializer and append an audit row (create).

    Args:
        view: DRF viewset (uses ``view.request`` and optional ``audit_module``).
        serializer: Validated serializer instance.
        **save_kwargs: Passed through to ``serializer.save``.

    Returns:
        The saved model instance.

    Side effects:
        One ``AuditLog`` create action; changes payload uses ``serializer.data``
        when available.
    """
    from accounts.models import AuditLog

    instance = serializer.save(**save_kwargs)
    changes = {}
    try:
        changes['__created__'] = dict(serializer.data)
    except Exception:
        pass
    log_audit(
        view.request,
        AuditLog.ACTION_CREATE,
        instance,
        module=_module_for(view, instance),
        changes=changes,
    )
    return instance


def audited_perform_update(
    view,
    serializer,
    *,
    before: Model | None = None,
    **save_kwargs,
) -> Model:
    """
    Save via serializer and append an audit row (update).

    Args:
        view: DRF viewset providing ``request`` and optional ``audit_module``.
        serializer: Validated serializer with ``instance`` set.
        before: Optional pre-save instance; defaults to ``serializer.instance``.
        **save_kwargs: Passed to ``serializer.save``.

    Returns:
        Updated model instance after save.

    Side effects:
        ``AuditLog`` update with field diff from in-memory snapshots.
    """
    from accounts.models import AuditLog

    if before is None:
        before = serializer.instance
    before_snapshot = _snapshot(before)
    instance = serializer.save(**save_kwargs)
    log_audit(
        view.request,
        AuditLog.ACTION_UPDATE,
        instance,
        module=_module_for(view, instance),
        changes=_diff_snapshots(before_snapshot, instance),
    )
    return instance


def audited_perform_destroy(view, instance: Model) -> None:
    """
    Delete instance and append an audit row (delete).

    Args:
        view: DRF viewset with ``request``.
        instance: Row to delete via ``DestroyModelMixin.perform_destroy``.

    Returns:
        None.

    Side effects:
        Deletes the DB row and writes ``AuditLog`` with ``__deleted__`` snapshot.
    """
    from accounts.models import AuditLog
    from rest_framework.mixins import DestroyModelMixin

    snapshot = _snapshot(instance)
    object_repr = snapshot.get('__str__', str(instance)[:255])
    module = _module_for(view, instance)
    DestroyModelMixin.perform_destroy(view, instance)
    log_audit(
        view.request,
        AuditLog.ACTION_DELETE,
        None,
        module=module,
        object_repr=object_repr,
        changes={'__deleted__': snapshot},
    )


def log_domain_event(
    request,
    action: str,
    instance: Model | None = None,
    *,
    module: str = '',
    changes: dict | None = None,
    object_repr: str | None = None,
) -> None:
    """
    Record a domain-specific audit event (custom create, @action, service).

    Args:
        request: DRF/Django request for actor/IP/path; may be None for jobs.
        action: Short verb (``create``, ``stock_adjust``, ``assign_role``, …).
            Prefer ``AuditLog.ACTION_*`` when it fits; free strings allowed.
        instance: Related model instance, or None for non-object events.
        module: Permission module string (``sales``, ``payroll``, …). Empty
            falls back to the instance app label inside ``log_audit``.
        changes: JSON-serializable payload (diffs, before/after, ids).
        object_repr: Optional display string; defaults to ``str(instance)``.

    Returns:
        None. Logging errors are swallowed so the business write is not blocked.

    Bounds:
        ``action`` length should fit ``AuditLog.action`` (max 32). Large
        ``changes`` dicts should stay modest (no binary blobs).
    """
    log_audit(
        request,
        action,
        instance,
        module=module,
        changes=changes,
        object_repr=object_repr,
    )


def log_model_change(
    request,
    action: str,
    instance: Model,
    *,
    module: str,
    before: Model | None = None,
) -> None:
    """
    Log create/update using ``diff_instance`` when a before row exists.

    Args:
        request: Actor request forwarded to ``log_domain_event``.
        action: Audit verb (often ``AuditLog.ACTION_*``).
        instance: Saved model instance after change.
        module: Permission module string stored on the log row.
        before: Pre-change instance for updates; omit on create-only logging.

    Returns:
        None.
    """
    changes = diff_instance(before, instance) if before else {}
    log_domain_event(request, action, instance, module=module, changes=changes)


def safe_serializer_data(serializer: serializers.BaseSerializer) -> dict:
    """
    Read serializer output without failing audit paths.

    Args:
        serializer: DRF serializer (validated or not).

    Returns:
        ``dict(serializer.data)`` or ``{}`` on any access/serialization error.
    """
    try:
        return dict(serializer.data)
    except Exception:
        return {}
