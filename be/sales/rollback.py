"""Full reversal of a completed sale (stock, wallet, journals)."""

from __future__ import annotations

from django.core.exceptions import ValidationError

from sales.models import Sale, SaleRefund
from sales.refunds import SaleRefundService


def sale_is_rollbackable(sale: Sale) -> bool:
    status = getattr(sale, 'refund_status', 'none') or 'none'
    return sale.status == 'completed' and status == 'none'


def sale_has_pending_rollback(sale: Sale) -> bool:
    annotated = getattr(sale, '_has_pending_rollback', None)
    if annotated is not None:
        return bool(annotated)
    from approvals.models import PendingChange
    from approvals.registry import ACTION_SALE_ROLLBACK

    return PendingChange.objects.filter(
        action_type=ACTION_SALE_ROLLBACK,
        entity_type='sales.Sale',
        entity_id=str(sale.pk),
        status=PendingChange.STATUS_PENDING,
    ).exists()


def annotate_sale_rollback_pending(queryset):
    """Batch pending rollback flags for list views (avoids per-row Exists)."""
    from django.db.models import CharField, Exists, OuterRef
    from django.db.models.functions import Cast

    from approvals.models import PendingChange
    from approvals.registry import ACTION_SALE_ROLLBACK

    pending = PendingChange.objects.filter(
        action_type=ACTION_SALE_ROLLBACK,
        entity_type='sales.Sale',
        status=PendingChange.STATUS_PENDING,
        entity_id=Cast(OuterRef('pk'), output_field=CharField()),
    )
    return queryset.annotate(_has_pending_rollback=Exists(pending))


def rollback_sale(*, sale: Sale, reason: str, user) -> SaleRefund:
    """Undo a mistaken sale. Original row stays; net stock and books go to zero."""
    reason = (reason or '').strip()
    if not reason:
        raise ValidationError({'reason': 'A reason is required to roll back a sale.'})
    if sale.status != 'completed':
        raise ValidationError('Only completed sales can be rolled back.')
    if not sale_is_rollbackable(sale):
        raise ValidationError(
            'This sale already has a refund. Use refund for remaining items, '
            'or it is already reversed.'
        )

    refund = SaleRefundService().create_refund(
        sale,
        reason=f'[ROLLBACK] {reason}',
        user=user,
        full=True,
    )
    refund.refund_type = 'rollback'
    refund.save(update_fields=['refund_type'])
    return refund
