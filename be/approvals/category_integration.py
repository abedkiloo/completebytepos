"""Maker-checker hooks for Category delete / deactivate."""

from __future__ import annotations

from django.core.exceptions import ValidationError

from approvals.models import PendingChange
from approvals.permissions import is_maker_checker_enabled
from approvals.registry import ACTION_CATEGORY_DEACTIVATE, ACTION_CATEGORY_DELETE
from approvals.service import snapshot_model, submit_change


def queue_category_deactivate(request, category) -> PendingChange:
    if not is_maker_checker_enabled():
        raise ValidationError('Maker-checker is not enabled.')
    reason = (
        request.data.get('change_reason')
        or request.data.get('reason')
        or ''
    )
    if not str(reason).strip():
        raise ValidationError({'reason': 'A reason is required to deactivate a category.'})
    return submit_change(
        request=request,
        action_type=ACTION_CATEGORY_DEACTIVATE,
        entity_type='products.Category',
        entity_id=category.pk,
        entity_repr=str(category),
        original_values={'is_active': category.is_active},
        proposed_values={'is_active': False},
        reason=str(reason).strip(),
    )


def queue_category_delete(request, category) -> PendingChange:
    if not is_maker_checker_enabled():
        raise ValidationError('Maker-checker is not enabled.')
    reason = (
        request.data.get('change_reason')
        or request.data.get('reason')
        or ''
    )
    if not str(reason).strip():
        raise ValidationError({'reason': 'A reason is required to delete a category.'})
    return submit_change(
        request=request,
        action_type=ACTION_CATEGORY_DELETE,
        entity_type='products.Category',
        entity_id=category.pk,
        entity_repr=str(category),
        original_values=snapshot_model(category),
        proposed_values={'__delete__': True},
        reason=str(reason).strip(),
    )
