"""Maker-checker hooks for store and module settings."""

from __future__ import annotations

from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError

from approvals.models import PendingChange
from approvals.permissions import is_maker_checker_enabled
from approvals.registry import (
    ACTION_PAYMENT_METHODS,
    ACTION_RECEIPT_LEGAL,
    ACTION_ROLE_PERMISSIONS,
    ACTION_STORE_SETTINGS,
)
from approvals.service import snapshot_model, submit_change

# Always apply immediately — avoids lock-out (cannot enable MC via pending MC).
STORE_SETTINGS_IMMEDIATE_FIELDS = frozenset({
    'maker_checker_enabled',
    'maker_checker_sales_controls',
    'emergency_stock_mode',
    'updated_by',
    'receipt_logo',
})

PAYMENT_METHOD_FIELDS = frozenset({'enabled_payment_methods'})
RECEIPT_LEGAL_FIELDS = frozenset({'receipt_header_text', 'receipt_footer_text'})
STORE_RULE_FIELDS = frozenset({
    'allow_sales_add_products',
    'sales_catalog_skip_pricing',
    'hide_entity_status_toggles',
    'receipt_show_logo',
    'receipt_show_sku',
    'receipt_auto_print',
})


def _action_for_field(key: str) -> Optional[str]:
    if key in PAYMENT_METHOD_FIELDS:
        return ACTION_PAYMENT_METHODS
    if key in RECEIPT_LEGAL_FIELDS:
        return ACTION_RECEIPT_LEGAL
    if key in STORE_RULE_FIELDS:
        return ACTION_STORE_SETTINGS
    return None


def classify_store_settings_changes(
    validated: Dict[str, Any],
    *,
    submitted_keys: set[str],
) -> Dict[str, Dict[str, Any]]:
    """Map action_type -> proposed field slice."""
    grouped: Dict[str, Dict[str, Any]] = {}
    for key, value in validated.items():
        if key not in submitted_keys or key in STORE_SETTINGS_IMMEDIATE_FIELDS:
            continue
        action = _action_for_field(key)
        if not action:
            continue
        grouped.setdefault(action, {})[key] = value
    return grouped


def queue_store_settings_patch(
    request,
    store,
    validated: Dict[str, Any],
    *,
    submitted_keys: set[str],
    reason: str,
) -> Optional[PendingChange]:
    if not is_maker_checker_enabled():
        return None

    grouped = classify_store_settings_changes(validated, submitted_keys=submitted_keys)
    if not grouped:
        return None

    import uuid

    batch_id = str(uuid.uuid4()) if len(grouped) > 1 else ''
    original = snapshot_model(store)
    first = None
    for action_type, proposed in grouped.items():
        ch = submit_change(
            request=request,
            action_type=action_type,
            entity_type='settings.StoreSettings',
            entity_id=store.pk,
            entity_repr='Store settings',
            original_values={k: original.get(k) for k in proposed},
            proposed_values=proposed,
            reason=reason,
            batch_id=batch_id,
        )
        if first is None:
            first = ch
    return first


def queue_module_settings_patch(
    request,
    *,
    module_name: str,
    updates: Dict[str, Any],
    reason: str,
) -> Optional[PendingChange]:
    if not is_maker_checker_enabled() or not updates:
        return None

    from settings.settings_service import SettingsService

    original = {}
    for key in updates:
        original[key] = SettingsService.get(module_name, key)

    return submit_change(
        request=request,
        action_type=ACTION_STORE_SETTINGS,
        entity_type='settings.ModuleSetting',
        entity_id=module_name,
        entity_repr=f'Module settings: {module_name}',
        original_values=original,
        proposed_values=updates,
        reason=reason,
        apply_payload={'module': module_name, 'updates': updates},
    )


def queue_role_permission_assign(
    request,
    role,
    permission_ids: list[int],
    *,
    reason: str,
) -> PendingChange:
    if not is_maker_checker_enabled():
        raise ValidationError('Maker-checker is not enabled.')

    original_ids = sorted(role.permissions.values_list('id', flat=True))
    proposed_ids = sorted(int(x) for x in permission_ids)

    return submit_change(
        request=request,
        action_type=ACTION_ROLE_PERMISSIONS,
        entity_type='accounts.Role',
        entity_id=role.pk,
        entity_repr=str(role),
        original_values={'permission_ids': original_ids},
        proposed_values={'permission_ids': proposed_ids},
        reason=reason,
        apply_payload={'permission_ids': proposed_ids},
    )
