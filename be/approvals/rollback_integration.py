"""Queue sale rollbacks for admin approval before stock and books change."""

from __future__ import annotations

from django.core.exceptions import ValidationError

from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_ROLLBACK
from approvals.service import submit_change
from sales.models import Sale
from sales.rollback import sale_has_pending_rollback, sale_is_rollbackable


def queue_sale_rollback(request, sale: Sale, *, reason: str) -> PendingChange:
    reason = (reason or '').strip()
    if not reason:
        raise ValidationError({'reason': 'A reason is required to roll back a sale.'})
    if not sale_is_rollbackable(sale):
        raise ValidationError(
            'This sale cannot be rolled back. It must be completed with no refund yet.'
        )
    if sale_has_pending_rollback(sale):
        raise ValidationError(
            'A rollback for this sale is already awaiting admin approval. '
            'Approve or reject it before submitting another.'
        )

    return submit_change(
        request=request,
        action_type=ACTION_SALE_ROLLBACK,
        entity_type='sales.Sale',
        entity_id=sale.pk,
        entity_repr=str(sale.sale_number or sale.pk),
        original_values={
            'sale_total': str(sale.total),
            'refund_status': sale.refund_status,
            'amount_paid': str(sale.amount_paid),
        },
        proposed_values={
            'rollback_mode': 'Full rollback',
            'amount': str(sale.total),
            'effect': 'Stock, wallet, and journals reversed after admin approval',
        },
        reason=reason,
        apply_payload={'full': True},
        require_maker_checker=False,
    )
