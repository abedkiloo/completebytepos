"""Hook helpers for viewsets — split sensitive vs immediate writes."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from django.core.exceptions import ValidationError

from approvals.models import PendingChange
from approvals.permissions import is_maker_checker_enabled
from approvals.registry import PRODUCT_SENSITIVE_FIELDS
from approvals.registry import ACTION_PRODUCT_DELETE
from approvals.service import route_product_sensitive_update, snapshot_model, submit_change


def split_product_payload(
    validated: Dict[str, Any],
    *,
    submitted_keys: set[str] | None = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Only treat fields the client sent as sensitive — not values auto-filled in validate().
    """
    keys = submitted_keys or set(validated.keys())
    sensitive = {}
    immediate = {}
    for key, value in validated.items():
        if key in PRODUCT_SENSITIVE_FIELDS and key in keys:
            sensitive[key] = value
        else:
            immediate[key] = value
    return sensitive, immediate


def queue_product_sensitive_update(
    request,
    product,
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
        raise ValidationError({'reason': 'A reason is required for price, stock, or status changes.'})
    return route_product_sensitive_update(
        request,
        product,
        sensitive,
        reason=str(reason).strip(),
    )


def queue_product_delete(request, product) -> PendingChange:
    if not is_maker_checker_enabled():
        raise ValidationError('Maker-checker is not enabled.')
    reason = (
        request.data.get('change_reason')
        or request.data.get('reason')
        or ''
    )
    if not str(reason).strip():
        raise ValidationError({'reason': 'A reason is required to delete a product.'})
    return submit_change(
        request=request,
        action_type=ACTION_PRODUCT_DELETE,
        entity_type='products.Product',
        entity_id=product.pk,
        entity_repr=str(product),
        original_values=snapshot_model(product),
        proposed_values={'__delete__': True},
        reason=str(reason).strip(),
    )
