"""Queue cashier sales for manager approval before stock, books, or receipts."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError

from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_COMPLETE
from approvals.service import submit_change
from sales.models import Sale

WAITING_MESSAGE = (
    'A manager will approve this sale so you can issue the receipt.'
)
APPROVED_MESSAGE_TEMPLATE = (
    'Sale #{sale_number} was approved. You can issue the receipt now.'
)
REJECTED_MESSAGE_TEMPLATE = (
    'Sale #{sale_number} was returned. Check Daily notes for the comment, '
    'fix it on POS, and send it again.'
)
QUEUE_REASON = 'Sale awaiting manager approval so the cashier can issue a receipt.'


def user_can_complete_sales(user) -> bool:
    """True when the user may finalise a sale (stock, books, receipt)."""
    if not user or not getattr(user, 'is_authenticated', True):
        return True
    if getattr(user, 'is_superuser', False):
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return True
    if getattr(profile, 'custom_role_id', None):
        return bool(profile.has_permission('sales', 'approve'))
    if getattr(profile, 'role', None) in ('super_admin', 'admin', 'manager'):
        return True
    return False


def sale_completion_should_wait(user) -> bool:
    return not user_can_complete_sales(user)


def pending_sale_complete_change(sale: Sale) -> PendingChange | None:
    return (
        PendingChange.objects.filter(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            status=PendingChange.STATUS_PENDING,
        )
        .order_by('-id')
        .first()
    )


def payment_payload_from_inputs(
    *,
    payment_method: str,
    amount_paid,
    allow_partial: bool = False,
    excess_payment_choice: str = 'change',
    use_wallet: bool = False,
    wallet_amount=None,
    payment_reference: str = '',
    sale_type: str = 'pos',
    client_channel: str = '',
) -> dict:
    return {
        'payment_method': payment_method or 'cash',
        'amount_paid': str(amount_paid or '0'),
        'allow_partial': bool(allow_partial),
        'excess_payment_choice': excess_payment_choice or 'change',
        'use_wallet': bool(use_wallet),
        'wallet_amount': str(wallet_amount or '0'),
        'payment_reference': payment_reference or '',
        'sale_type': sale_type or 'pos',
        'client_channel': client_channel or '',
    }


def queue_sale_complete(request, sale: Sale, *, payment_payload: dict | None = None) -> PendingChange:
    existing = pending_sale_complete_change(sale)
    if existing:
        return existing
    payload = payment_payload or {}
    change = submit_change(
        request=request,
        action_type=ACTION_SALE_COMPLETE,
        entity_type='sales.Sale',
        entity_id=sale.pk,
        entity_repr=sale.sale_number or str(sale.pk),
        original_values={'status': sale.status, 'total': str(sale.total)},
        proposed_values={
            'status': 'completed',
            'total': str(sale.total),
            'payment_method': payload.get('payment_method') or sale.payment_method,
            'effect': 'Stock, payment, and books apply after manager approval',
        },
        reason=QUEUE_REASON,
        apply_payload=payload,
        require_maker_checker=False,
    )
    from daily_notes.approval_notice import (
        complete_sale_return_notes,
        notify_managers_for_change,
    )

    notify_managers_for_change(
        author=getattr(request, 'user', None),
        change=change,
        sale=sale,
    )
    complete_sale_return_notes(record_id=sale.pk)
    return change


def cancel_queued_sale(sale: Sale) -> Sale:
    if sale.status != 'pending_approval':
        return sale
    sale.status = 'cancelled'
    sale.save(update_fields=['status', 'updated_at'])
    return sale


def return_queued_sale_for_correction(sale: Sale) -> Sale:
    """Put a rejected sale back on the cashier's POS cart so they can fix it."""
    if sale.status != 'pending_approval':
        return sale
    sale.status = 'holding'
    sale.save(update_fields=['status', 'updated_at'])
    return sale


def restore_queued_sale_for_approval(sale: Sale, change: PendingChange | None = None) -> Sale:
    """Re-queue a holding sale after the salesperson sends it back."""
    if sale.status != 'holding':
        return sale
    sale.status = 'pending_approval'
    sale.save(update_fields=['status', 'updated_at'])
    if change is None:
        return sale
    existing = change.apply_payload or {}
    change.apply_payload = {
        **existing,
        **payment_payload_from_inputs(
            payment_method=sale.payment_method or existing.get('payment_method') or 'cash',
            amount_paid=sale.amount_paid if sale.amount_paid is not None else existing.get('amount_paid') or '0',
            allow_partial=bool(existing.get('allow_partial')),
            excess_payment_choice=existing.get('excess_payment_choice') or 'change',
            use_wallet=bool(existing.get('use_wallet')),
            wallet_amount=existing.get('wallet_amount') or '0',
            payment_reference=sale.payment_reference or existing.get('payment_reference') or '',
            sale_type=existing.get('sale_type') or sale.sale_type or 'pos',
            client_channel=existing.get('client_channel') or getattr(sale, 'client_channel', '') or '',
        ),
    }
    change.save(update_fields=['apply_payload'])
    return sale


def complete_queued_sale(sale: Sale, user, payload: dict | None = None) -> Sale:
    """Re-check stock, move inventory, apply payment, post the journal."""
    if sale.status != 'pending_approval':
        raise ValidationError('This sale is not waiting for approval.')

    from sales.module_settings import sales_validate_stock_before_sale
    from sales.services import SaleService

    service = SaleService()
    items_data = [
        {
            'product_id': item.product_id,
            'variant_id': item.variant_id,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
        }
        for item in sale.items.select_related('product', 'variant')
    ]
    if not items_data:
        raise ValidationError('Cannot complete an empty sale.')

    validated_items = service.validate_sale_items(
        items_data,
        check_stock=sales_validate_stock_before_sale(),
        user=user,
    )

    payload = payload or {}
    customer = sale.customer
    amount_paid = Decimal(str(payload.get('amount_paid', sale.amount_paid or 0)))
    payment_result = service._prepare_sale_payment(
        customer=customer,
        sale_type=payload.get('sale_type') or sale.sale_type or 'pos',
        total=sale.total,
        amount_paid=amount_paid,
        allow_partial=bool(payload.get('allow_partial')),
        excess_payment_choice=payload.get('excess_payment_choice') or 'change',
        use_wallet=bool(payload.get('use_wallet')),
        wallet_amount_requested=Decimal(str(payload.get('wallet_amount') or 0)),
    )

    for item_data in validated_items:
        if item_data['product'].track_stock and sales_validate_stock_before_sale():
            service._create_sale_stock_movements(
                branch=sale.branch,
                user=user,
                reference=sale.sale_number,
                notes=f'Sale {sale.sale_number}',
                product=item_data['product'],
                variant=item_data['variant'],
                quantity=item_data['quantity'],
                unit_cost=item_data['unit_cost'],
            )

    payment_method = payload.get('payment_method') or sale.payment_method
    payment_reference = payload.get('payment_reference')
    if payment_reference is None:
        payment_reference = sale.payment_reference
    sale.payment_method = payment_method
    sale.payment_reference = payment_reference or ''
    sale.status = 'completed'
    sale.save(update_fields=[
        'payment_method',
        'payment_reference',
        'status',
        'updated_at',
    ])

    service._apply_sale_payment(customer, sale, user, payment_result)

    try:
        from accounting.services import create_sale_journal_entry

        create_sale_journal_entry(sale)
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            'Error creating journal entry for approved sale %s', sale.sale_number
        )

    notify_cashier_sale_approved(sale, user)
    from daily_notes.approval_notice import SOURCE_SALE_COMPLETE, complete_manager_queue_notes

    complete_manager_queue_notes(source=SOURCE_SALE_COMPLETE, record_id=sale.pk)
    return sale


def approved_receipt_message(sale: Sale) -> str:
    return APPROVED_MESSAGE_TEMPLATE.format(sale_number=sale.sale_number)


def notify_cashier_sale_approved(sale: Sale, checker) -> None:
    from daily_notes.approval_notice import notify_sale_approved

    notify_sale_approved(sale=sale, checker=checker)
    try:
        from agents.push import get_push_notifier

        get_push_notifier().notify(
            user_id=sale.cashier_id,
            title='Sale approved',
            body=approved_receipt_message(sale),
            data={
                'sale_id': sale.id,
                'sale_number': sale.sale_number,
                'type': 'sale_complete',
            },
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            'Could not push sale-approved notice for %s', sale.sale_number
        )


def notify_cashier_sale_rejected(sale: Sale, checker, reason: str = '') -> None:
    try:
        from agents.push import get_push_notifier

        get_push_notifier().notify(
            user_id=sale.cashier_id,
            title='Sale not approved',
            body=REJECTED_MESSAGE_TEMPLATE.format(sale_number=sale.sale_number),
            data={
                'sale_id': sale.id,
                'sale_number': sale.sale_number,
                'type': 'sale_complete_rejected',
                'reason': reason or '',
            },
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            'Could not push sale-rejected notice for %s', sale.sale_number
        )
