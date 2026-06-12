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
    """Save via serializer and append an audit row (create)."""
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
    """Save via serializer and append an audit row (update)."""
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
    """Delete instance and append an audit row (delete)."""
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
    """One-liner for custom creates, @action handlers, and service callbacks."""
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
    """Log create/update using model diff when before snapshot is available."""
    changes = diff_instance(before, instance) if before else {}
    log_domain_event(request, action, instance, module=module, changes=changes)


def safe_serializer_data(serializer: serializers.BaseSerializer) -> dict:
    try:
        return dict(serializer.data)
    except Exception:
        return {}
