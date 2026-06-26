"""Queue sale refunds for maker-checker approval."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError

from approvals.models import PendingChange
from approvals.permissions import is_maker_checker_enabled
from approvals.registry import ACTION_SALE_REFUND
from approvals.service import submit_change
from sales.models import Sale
from sales.refunds import SaleRefundService


def sale_refund_maker_checker_active() -> bool:
    return is_maker_checker_enabled()


def _summarize_refund_lines(sale: Sale, items: Optional[List[Dict[str, Any]]], *, full: bool) -> str:
    service = SaleRefundService()
    try:
        lines = service._resolve_refund_lines(sale, items=items, full=full)
    except ValidationError:
        return '—'
    parts = []
    for line in lines:
        item = line['sale_item']
        name = getattr(item.product, 'name', None) or 'Item'
        variant_bits = []
        if getattr(item, 'size', None):
            variant_bits.append(item.size.name)
        if getattr(item, 'color', None):
            variant_bits.append(item.color.name)
        label = name
        if variant_bits:
            label = f'{name} ({", ".join(variant_bits)})'
        parts.append(f'{label} × {line["quantity"]}')
    return '; '.join(parts) if parts else '—'


def _estimate_refund_amount(sale: Sale, items: Optional[List[Dict[str, Any]]], *, full: bool) -> Decimal:
    service = SaleRefundService()
    lines = service._resolve_refund_lines(sale, items=items, full=full)
    return sum((line['subtotal'] for line in lines), Decimal('0'))


def queue_sale_refund(
    request,
    sale: Sale,
    *,
    full: bool,
    items: Optional[List[Dict[str, Any]]],
    reason: str,
) -> PendingChange:
    if not sale_refund_maker_checker_active():
        raise ValidationError('Maker-checker is not enabled.')

    if sale.status != 'completed':
        raise ValidationError('Only completed sales can be refunded.')
    if sale.refund_status == 'refunded':
        raise ValidationError('This sale has already been fully refunded.')

    pending_exists = PendingChange.objects.filter(
        action_type=ACTION_SALE_REFUND,
        entity_type='sales.Sale',
        entity_id=str(sale.pk),
        status=PendingChange.STATUS_PENDING,
    ).exists()
    if pending_exists:
        raise ValidationError(
            'A refund for this sale is already awaiting approval. '
            'Approve or reject it before submitting another.'
        )

    # Validate payload before queueing.
    SaleRefundService()._resolve_refund_lines(sale, items=items, full=full)

    amount = _estimate_refund_amount(sale, items, full=full)
    mode_label = 'Full void' if full else 'Partial refund'
    lines_summary = _summarize_refund_lines(sale, items, full=full)

    return submit_change(
        request=request,
        action_type=ACTION_SALE_REFUND,
        entity_type='sales.Sale',
        entity_id=sale.pk,
        entity_repr=str(sale.sale_number or sale.pk),
        original_values={
            'sale_total': str(sale.total),
            'refund_status': sale.refund_status,
            'refundable_remaining': str(sale.refundable_remaining()),
        },
        proposed_values={
            'refund_mode': mode_label,
            'lines': lines_summary,
            'amount': str(amount),
        },
        reason=reason,
        apply_payload={
            'full': bool(full),
            'items': items or [],
        },
    )
