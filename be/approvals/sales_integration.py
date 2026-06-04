"""Optional maker-checker hooks for completed sale metadata edits."""

from __future__ import annotations

from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError

from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_COMPLETED_EDIT
from approvals.sales_policy import (
    SALE_EDIT_NOT_AVAILABLE_MESSAGE,
    filter_queueable_sale_fields,
    is_sales_maker_checker_active,
    sale_edit_has_unsupported_fields,
)
from approvals.service import snapshot_model, submit_change


def queue_completed_sale_edit(
    request,
    sale,
    proposed: Dict[str, Any],
    *,
    reason: str,
) -> PendingChange:
    if not is_sales_maker_checker_active():
        raise ValidationError('Optional sales maker-checker is not enabled.')

    if sale.status != 'completed':
        raise ValidationError('Only completed sales can use post-completion approval.')

    if sale_edit_has_unsupported_fields(proposed):
        raise ValidationError({'detail': SALE_EDIT_NOT_AVAILABLE_MESSAGE})

    queueable = filter_queueable_sale_fields(proposed)
    if not queueable:
        raise ValidationError({'detail': 'No supported fields to submit for approval.'})

    if not str(reason).strip():
        raise ValidationError({'reason': 'A reason is required for post-completion sale edits.'})

    original = snapshot_model(sale)
    return submit_change(
        request=request,
        action_type=ACTION_SALE_COMPLETED_EDIT,
        entity_type='sales.Sale',
        entity_id=sale.pk,
        entity_repr=str(sale.sale_number or sale.pk),
        original_values={k: original.get(k) for k in queueable},
        proposed_values=queueable,
        reason=str(reason).strip(),
    )
