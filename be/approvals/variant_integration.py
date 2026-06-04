"""Maker-checker hooks for ProductVariant writes."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from django.core.exceptions import ValidationError

from approvals.models import PendingChange
from approvals.permissions import is_maker_checker_enabled
from approvals.registry import (
    ACTION_PRODUCT_DELETE,
    VARIANT_SENSITIVE_FIELDS,
    classify_variant_field_changes,
)
from approvals.service import route_variant_sensitive_update, snapshot_model, submit_change


def split_variant_payload(
    validated: Dict[str, Any],
    *,
    submitted_keys: set[str] | None = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    keys = submitted_keys or set(validated.keys())
    sensitive = {}
    immediate = {}
    for key, value in validated.items():
        if key in VARIANT_SENSITIVE_FIELDS and key in keys:
            sensitive[key] = value
        else:
            immediate[key] = value
    return sensitive, immediate


def queue_variant_sensitive_update(
    request,
    variant,
    sensitive: Dict[str, Any],
) -> Optional[PendingChange]:
    if not sensitive or not is_maker_checker_enabled():
        return None
    reason = (
        request.data.get('change_reason')
        or request.data.get('reason')
        or ''
    )
    if not str(reason).strip():
        raise ValidationError(
            {'reason': 'A reason is required for variant price, stock, or status changes.'}
        )
    return route_variant_sensitive_update(
        request,
        variant,
        sensitive,
        reason=str(reason).strip(),
    )


def queue_variant_delete(request, variant) -> PendingChange:
    if not is_maker_checker_enabled():
        raise ValidationError('Maker-checker is not enabled.')
    reason = (
        request.data.get('change_reason')
        or request.data.get('reason')
        or ''
    )
    if not str(reason).strip():
        raise ValidationError({'reason': 'A reason is required to delete a variant.'})
    return submit_change(
        request=request,
        action_type=ACTION_PRODUCT_DELETE,
        entity_type='products.ProductVariant',
        entity_id=variant.pk,
        entity_repr=str(variant),
        original_values=snapshot_model(variant),
        proposed_values={'__delete__': True},
        reason=str(reason).strip(),
    )
