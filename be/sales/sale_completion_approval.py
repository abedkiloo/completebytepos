"""Queue cashier sales for manager approval before stock, books, or receipts."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_COMPLETE
from approvals.service import submit_change
from products.stock_utils import sellable_unit_cost
from sales.models import Sale, SaleItem

WAITING_MESSAGE = (
    'A manager will approve this sale. Stock, books, and the receipt update after they approve.'
)
APPROVED_MESSAGE_TEMPLATE = (
    'Sale #{sale_number} was approved and completed. You can print the receipt.'
)
REJECTED_MESSAGE_TEMPLATE = (
    'Sale #{sale_number} was returned. Check Daily notes for the comment, '
    'fix it on POS, and send it again.'
)
QUEUE_REASON = 'Sale recorded at the till, awaiting manager approval before stock and books.'
COMPLETE_NOT_READY = 'This sale is not waiting for approval or collection.'
CORRECTION_FINGERPRINT_KEY = 'correction_fingerprint'
UNEDITED_RETURN_MESSAGE = (
    'Update this sale before sending it back for approval.'
)
UNEDITED_RETURN_CONFIRM_HINT = (
    'Nothing changed since this sale was returned. '
    'Confirm you are sure the original sale is already correct, then send it again.'
)
ADMIN_OVERRIDE_REQUIRED = (
    'Only an admin can return an approved sale for correction.'
)
POSTED_RETURN_BLOCKED_REFUND = (
    'Refunded sales cannot be returned for correction.'
)
ADMIN_RETURN_NOT_ALLOWED = (
    'This sale cannot be returned for correction.'
)


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


def latest_rejected_sale_complete_change(sale: Sale) -> PendingChange | None:
    return (
        PendingChange.objects.filter(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            status=PendingChange.STATUS_REJECTED,
        )
        .order_by('-id')
        .first()
    )


def annotate_sale_approval_state(queryset):
    """Annotate sales with rejected/pending sale-complete flags for the queue."""
    from django.db.models import CharField, Exists, OuterRef, Subquery
    from django.db.models.functions import Cast

    rejected = PendingChange.objects.filter(
        action_type=ACTION_SALE_COMPLETE,
        entity_type='sales.Sale',
        status=PendingChange.STATUS_REJECTED,
        entity_id=Cast(OuterRef('pk'), output_field=CharField()),
    )
    pending = PendingChange.objects.filter(
        action_type=ACTION_SALE_COMPLETE,
        entity_type='sales.Sale',
        status=PendingChange.STATUS_PENDING,
        entity_id=Cast(OuterRef('pk'), output_field=CharField()),
    )
    return queryset.annotate(
        _has_rejected_sale_complete=Exists(rejected),
        _has_pending_sale_complete=Exists(pending),
        _sale_rejection_reason=Subquery(
            rejected.order_by('-id').values('rejection_reason')[:1]
        ),
    )


def awaiting_approval_queue_q():
    """Pending manager approval, plus rejected holdings waiting on the salesperson."""
    from django.db.models import Q

    return Q(status='pending_approval') | Q(
        status='holding',
        _has_rejected_sale_complete=True,
        _has_pending_sale_complete=False,
    )


def sale_needs_salesperson_action(sale: Sale) -> bool:
    if getattr(sale, 'status', None) != 'holding':
        return False
    annotated = getattr(sale, '_has_rejected_sale_complete', None)
    if annotated is not None:
        return bool(annotated) and not bool(getattr(sale, '_has_pending_sale_complete', False))
    if pending_sale_complete_change(sale):
        return False
    return latest_rejected_sale_complete_change(sale) is not None


def sale_must_requeue_after_correction(sale: Sale) -> bool:
    """
    True when checkout must go back to manager approval.

    Covers sales returned from pending_approval, awaiting_payment, or completed
    (already approved/posted). Managers/admins cannot skip the queue for these.
    """
    return sale_needs_salesperson_action(sale)


def sale_was_returned_from_completed(sale: Sale) -> bool:
    """True when this sale was already live and later returned for correction.

    First-time pending approvals (and manager rejects before completion) are
    False — the customer has not received a sale SMS yet. Posted corrections
    leave soft-voided ``#corrected`` stock movements and/or a rejected
    sale_complete change with ``returned_from_status=completed``.
    """
    sale_number = (getattr(sale, 'sale_number', None) or '').strip()
    if sale_number:
        from inventory.models import StockMovement

        if StockMovement.objects.filter(
            movement_type='sale',
            reference__startswith=f'{sale_number}#corrected',
        ).exists():
            return True

    change = latest_rejected_sale_complete_change(sale)
    if change is None:
        return False
    original = change.original_values or {}
    returned_from = (
        original.get('returned_from_status')
        or original.get('status')
        or ''
    )
    return str(returned_from).strip() == 'completed'


def payload_requests_customer_sms(payload: dict | None) -> bool:
    """Truthy ``notify_customer`` / ``send_customer_sms`` from an approve payload."""
    if not payload:
        return False
    raw = payload.get('notify_customer', payload.get('send_customer_sms'))
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return False
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def sale_rejection_reason(sale: Sale) -> str:
    if not sale_needs_salesperson_action(sale):
        return ''
    annotated = getattr(sale, '_sale_rejection_reason', None)
    if annotated:
        return str(annotated).strip()
    change = latest_rejected_sale_complete_change(sale)
    return (change.rejection_reason or '').strip() if change else ''


def sale_correction_fingerprint(sale: Sale) -> dict:
    """Snapshot items, customer, and totals so a resubmit requires a real edit."""
    items = []
    for item in sale.items.all().order_by('id'):
        items.append({
            'product_id': item.product_id,
            'variant_id': item.variant_id,
            'quantity': str(item.quantity or 0),
            'unit_price': str(item.unit_price or 0),
        })
    return {
        'items': items,
        'customer_id': sale.customer_id,
        'total': str(sale.total or 0),
        'discount_amount': str(sale.discount_amount or 0),
        'tax_amount': str(sale.tax_amount or 0),
        'amount_paid': str(sale.amount_paid or 0),
        'payment_method': sale.payment_method or '',
        'payment_reference': sale.payment_reference or '',
    }


def _normalize_correction_fingerprint(raw) -> dict:
    if not isinstance(raw, dict):
        return {}
    items = []
    for item in raw.get('items') or []:
        if not isinstance(item, dict):
            continue
        items.append({
            'product_id': item.get('product_id'),
            'variant_id': item.get('variant_id'),
            'quantity': str(item.get('quantity') or 0),
            'unit_price': str(item.get('unit_price') or 0),
        })
    return {
        'items': items,
        'customer_id': raw.get('customer_id'),
        'total': str(raw.get('total') or 0),
        'discount_amount': str(raw.get('discount_amount') or 0),
        'tax_amount': str(raw.get('tax_amount') or 0),
        'amount_paid': str(raw.get('amount_paid') or 0),
        'payment_method': str(raw.get('payment_method') or ''),
        'payment_reference': str(raw.get('payment_reference') or ''),
    }


def attach_correction_fingerprint(
    change: PendingChange,
    sale: Sale,
    previous_status: str | None = None,
) -> None:
    values = dict(change.original_values or {})
    values[CORRECTION_FINGERPRINT_KEY] = sale_correction_fingerprint(sale)
    if previous_status:
        values['returned_from_status'] = previous_status
    change.original_values = values
    change.save(update_fields=['original_values'])


def stored_correction_fingerprint(sale: Sale) -> dict | None:
    change = latest_rejected_sale_complete_change(sale)
    if change is None:
        return None
    raw = (change.original_values or {}).get(CORRECTION_FINGERPRINT_KEY)
    if not isinstance(raw, dict):
        return None
    return _normalize_correction_fingerprint(raw)


def returned_sale_was_edited(sale: Sale) -> bool:
    stored = stored_correction_fingerprint(sale)
    if stored is None:
        return True
    current = _normalize_correction_fingerprint(sale_correction_fingerprint(sale))
    return stored != current


def assert_returned_sale_was_edited(
    sale: Sale,
    *,
    confirm_unchanged: bool = False,
) -> None:
    """Block unedited resubmits unless the cashier explicitly confirms no change."""
    if not sale_needs_salesperson_action(sale):
        return
    if returned_sale_was_edited(sale):
        return
    if confirm_unchanged:
        return
    raise ValidationError(UNEDITED_RETURN_MESSAGE)


def record_rejected_sale_complete_change(
    sale: Sale,
    *,
    checker,
    reason: str,
    previous_status: str,
) -> PendingChange:
    return PendingChange.objects.create(
        action_type=ACTION_SALE_COMPLETE,
        entity_type='sales.Sale',
        entity_id=str(sale.pk),
        entity_repr=sale.sale_number or str(sale.pk),
        original_values={
            'status': previous_status,
            'total': str(sale.total or 0),
            CORRECTION_FINGERPRINT_KEY: sale_correction_fingerprint(sale),
            'returned_from_status': previous_status,
        },
        proposed_values={'status': 'holding'},
        reason=reason,
        status=PendingChange.STATUS_REJECTED,
        made_by=sale.cashier or sale.served_by or checker,
        checked_by=checker,
        checked_at=timezone.now(),
        rejection_reason=reason,
        apply_payload={},
    )


def reverse_sale_wallet_effects(sale: Sale, *, user, reason: str) -> None:
    """Undo wallet payment / debt / overpayment for a sale returned for correction.

    Creates a reverse ledger row and **invalidates** the originals (source_type
    flipped to ``other``) so re-completion can post fresh debt for the new
    unpaid total. Leaving active ``debt`` rows behind used to skip re-apply.
    """
    from sales.models import CustomerWalletTransaction

    customer = sale.customer
    if customer is None:
        return
    originals = list(
        CustomerWalletTransaction.objects.filter(
            sale=sale,
            source_type__in=('payment', 'overpayment', 'debt'),
        ).order_by('id')
    )
    if not originals:
        return
    customer.refresh_from_db()
    for txn in originals:
        amount = txn.amount or Decimal('0')
        if amount <= 0:
            continue
        if txn.transaction_type == 'debit':
            customer.wallet_balance += amount
            reverse_type = 'credit'
        else:
            customer.wallet_balance -= amount
            reverse_type = 'debit'
        customer.save(update_fields=['wallet_balance', 'updated_at'])
        CustomerWalletTransaction.objects.create(
            customer=customer,
            transaction_type=reverse_type,
            source_type='other',
            amount=amount,
            balance_after=customer.wallet_balance,
            sale=sale,
            reference=sale.sale_number,
            notes=f'Admin returned sale {sale.sale_number} for correction: {reason}',
            created_by=user,
        )
        # Drop the original out of active payment/debt so re-complete can post again.
        marker = f'[REVERSED for correction] {reason}'.strip()
        prior = (txn.notes or '').strip()
        txn.source_type = 'other'
        txn.notes = f'{prior} {marker}'.strip() if prior else marker
        txn.save(update_fields=['source_type', 'notes'])


def unpost_posted_sale(sale: Sale, *, user, reason: str) -> None:
    """Undo stock, wallet, and journals so the sale can be edited as a holding.

    Mirrors refund stock restore: FIFO layers return via allocation slices and
    return movements stamp ``SaleItem.unit_cost`` (not live catalog cost). Prior
    ``sale`` movements are retagged so COGS/reports never double-count after
    re-approval. Layer allocations are cleared so the next complete drains cleanly.
    """
    from inventory.models import StockMovement
    from accounting.reversal import reverse_source_documents
    from sales.models import SaleItemLayerAllocation
    from sales.refunds import SaleRefundService

    notes = f'Admin returned sale {sale.sale_number} for correction: {reason}'.strip()
    for item in sale.items.select_related('product', 'variant'):
        product = item.product
        if not product or not product.track_stock:
            continue
        refunded = item.refund_lines.aggregate(total=Sum('quantity'))['total'] or 0
        qty = int(item.quantity or 0) - int(refunded)
        if qty <= 0:
            continue
        SaleRefundService._return_stock(
            sale=sale,
            sale_item=item,
            quantity=qty,
            branch=sale.branch,
            user=user,
            reference=sale.sale_number,
            notes=notes,
        )

    # Soft-void prior sale drains so trading-profit movement fallbacks and
    # stock ledgers keep a clear correction trail without double COGS.
    if sale.sale_number:
        void_tag = timezone.now().strftime('%Y%m%d%H%M%S')
        void_ref = f'{sale.sale_number}#corrected-{void_tag}'
        StockMovement.objects.filter(
            movement_type='sale',
            reference=sale.sale_number,
        ).update(
            reference=void_ref,
            notes=f'{notes} (superseded sale drain)',
        )

    # Allocations already restored qty_returned; drop them so re-complete can
    # stamp fresh FIFO slices against the corrected cart.
    SaleItemLayerAllocation.objects.filter(sale_item__sale=sale).delete()

    reverse_source_documents('sale', sale.pk, reason=reason, user=user)
    reverse_sale_wallet_effects(sale, user=user, reason=reason)


def notify_sale_returned_for_correction(sale: Sale, checker, reason: str) -> None:
    from daily_notes.approval_notice import (
        SOURCE_SALE_COMPLETE,
        complete_manager_queue_notes,
        notify_approval_rejected,
    )

    requester = sale.cashier or sale.served_by
    notify_approval_rejected(
        requester=requester,
        checker=checker,
        action_type='sale_complete',
        entity_repr=sale.sale_number or str(sale.pk),
        rejection_reason=reason,
        source='sale_complete',
        record_id=sale.pk,
        is_sticky=True,
        sale=sale,
    )
    notify_cashier_sale_rejected(sale, checker, reason)
    complete_manager_queue_notes(source=SOURCE_SALE_COMPLETE, record_id=sale.pk)


def _truthy_flag(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def clear_sale_tender_fields(sale: Sale) -> None:
    """Zero till payment so the sale reads as unpaid after an admin correction."""
    sale.amount_paid = Decimal('0')
    sale.change = Decimal('0')
    sale.payment_reference = ''
    sale.save(update_fields=['amount_paid', 'change', 'payment_reference', 'updated_at'])


@transaction.atomic
def admin_return_sale_for_correction(
    sale: Sale,
    *,
    user,
    reason: str,
    clear_payment: bool = False,
) -> Sale:
    """Admin-only: send an approved or posted sale back to the seller for editing.

    ``clear_payment`` removes an erroneous till payment (amount paid → 0) after
    books/wallet are reversed, so Terminal opens unpaid and the customer is not
    left looking paid. The correction fingerprint still records the old tender.
    """
    from approvals.permissions import user_has_admin_checker_override

    if not user_has_admin_checker_override(user):
        raise ValidationError(ADMIN_OVERRIDE_REQUIRED)
    reason = (reason or '').strip()
    if not reason:
        raise ValidationError({'rejection_reason': 'Rejection reason is required.'})
    previous = sale.status
    if previous == 'completed':
        refund_status = getattr(sale, 'refund_status', 'none') or 'none'
        if refund_status != 'none':
            raise ValidationError(POSTED_RETURN_BLOCKED_REFUND)
        unpost_posted_sale(sale, user=user, reason=reason)
    elif previous != 'awaiting_payment':
        raise ValidationError(ADMIN_RETURN_NOT_ALLOWED)

    pending = pending_sale_complete_change(sale)
    if pending:
        pending.status = PendingChange.STATUS_REJECTED
        pending.checked_by = user
        pending.checked_at = timezone.now()
        pending.rejection_reason = reason
        pending.save(update_fields=[
            'status', 'checked_by', 'checked_at', 'rejection_reason',
        ])

    sale.refresh_from_db()
    fingerprint_source_status = previous
    sale.status = 'holding'
    sale.save(update_fields=['status', 'updated_at'])
    # Fingerprint while the old tender is still on the sale, then clear if asked.
    record_rejected_sale_complete_change(
        sale,
        checker=user,
        reason=reason,
        previous_status=fingerprint_source_status,
    )
    if clear_payment:
        clear_sale_tender_fields(sale)
    notify_sale_returned_for_correction(sale, user, reason)
    return sale


WALLET_CHANGED_MESSAGE = (
    '{customer} now has KES {balance} in their wallet, but this sale was sent '
    'using KES {locked} from the wallet. Return the sale to the salesperson to '
    'update the payment.'
)

INVOICE_PAYLOAD_KEYS = (
    'create_invoice',
    'customer_name',
    'customer_email',
    'customer_phone',
    'customer_address',
    'due_date',
    'notes',
    'create_payment_plan',
    'number_of_installments',
    'installment_frequency',
    'payment_plan_start_date',
)


def wallet_amount_to_lock(customer, total, *, use_wallet: bool, requested=None) -> Decimal:
    """Wallet money the salesperson's sale uses, fixed at send time."""
    if not customer or not use_wallet:
        return Decimal('0')
    balance = customer.wallet_balance or Decimal('0')
    if balance <= 0:
        return Decimal('0')
    requested = Decimal(str(requested or 0))
    total = Decimal(str(total or 0))
    if requested > 0:
        return min(requested, balance, total)
    return min(balance, total)


def invoice_payload_from_validated_data(validated_data: dict) -> dict | None:
    """JSON-safe invoice options so approval can create the invoice later."""
    sale_type = validated_data.get('sale_type', 'pos')
    if sale_type != 'normal' and not validated_data.get('create_invoice'):
        return None
    payload = {}
    for key in INVOICE_PAYLOAD_KEYS:
        value = validated_data.get(key)
        if value is None or value == '':
            continue
        if hasattr(value, 'isoformat'):
            value = value.isoformat()
        payload[key] = value
    return payload


def _invoice_validated_data(sale: Sale, payload: dict) -> dict | None:
    from django.utils.dateparse import parse_date

    raw = payload.get('invoice')
    if raw is None:
        return None
    data = dict(raw)
    for key in ('due_date', 'payment_plan_start_date'):
        if isinstance(data.get(key), str):
            data[key] = parse_date(data[key])
    data['sale_type'] = payload.get('sale_type') or sale.sale_type or 'pos'
    data['payment_method'] = payload.get('payment_method') or sale.payment_method
    return data


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
    wallet_amount_locked=None,
    invoice: dict | None = None,
) -> dict:
    payload = {
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
    if wallet_amount_locked is not None:
        payload['wallet_amount_locked'] = str(wallet_amount_locked)
    if invoice is not None:
        payload['invoice'] = invoice
    return payload


def queue_sale_complete(
    request,
    sale: Sale,
    *,
    payment_payload: dict | None = None,
    confirm_unchanged: bool = False,
) -> PendingChange:
    existing = pending_sale_complete_change(sale)
    if existing:
        return existing
    assert_returned_sale_was_edited(sale, confirm_unchanged=confirm_unchanged)
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
            'effect': 'Payment recorded at the till; stock and books post after manager approval',
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
    from daily_notes.approval_notice import SOURCE_SALE_COMPLETE, complete_manager_queue_notes

    complete_manager_queue_notes(source=SOURCE_SALE_COMPLETE, record_id=sale.pk)
    return sale


def return_queued_sale_for_correction(sale: Sale) -> Sale:
    """Put a rejected sale back on the cashier's POS cart so they can fix it."""
    if sale.status != 'pending_approval':
        return sale
    sale.status = 'holding'
    sale.save(update_fields=['status', 'updated_at'])
    return sale


def _resubmitted_amount_paid(sale: Sale, change: PendingChange, existing: dict) -> Decimal:
    """Use the till amount on the holding after correction — never reinflate unpaid.

    Older logic fell back to the previous ``apply_payload`` amount when the holding
    showed ``0``, which made unpaid / debt-only corrections look fully paid again
    after resubmit. The salesperson's current ``sale.amount_paid`` is authoritative.
    """
    del change, existing  # kept for call-site compatibility
    return max(Decimal('0'), Decimal(str(sale.amount_paid or 0)))


def restore_queued_sale_for_approval(sale: Sale, change: PendingChange | None = None) -> Sale:
    """Re-queue a holding sale after the salesperson sends it back."""
    if sale.status != 'holding':
        return sale
    sale.status = 'pending_approval'
    sale.save(update_fields=['status', 'updated_at'])
    if change is None:
        return sale
    existing = change.apply_payload or {}
    use_wallet = bool(existing.get('use_wallet'))
    wallet_amount = existing.get('wallet_amount') or '0'
    change.apply_payload = {
        **existing,
        **payment_payload_from_inputs(
            payment_method=sale.payment_method or existing.get('payment_method') or 'cash',
            amount_paid=_resubmitted_amount_paid(sale, change, existing),
            allow_partial=bool(existing.get('allow_partial')),
            excess_payment_choice=existing.get('excess_payment_choice') or 'change',
            use_wallet=use_wallet,
            wallet_amount=wallet_amount,
            payment_reference=sale.payment_reference or existing.get('payment_reference') or '',
            sale_type=existing.get('sale_type') or sale.sale_type or 'pos',
            client_channel=existing.get('client_channel') or getattr(sale, 'client_channel', '') or '',
            wallet_amount_locked=wallet_amount_to_lock(
                sale.customer, sale.total, use_wallet=use_wallet, requested=wallet_amount,
            ),
        ),
    }
    change.save(update_fields=['apply_payload'])
    return sale


def approve_queued_sale(
    sale: Sale,
    user=None,
    *,
    notify_customer: bool | None = None,
) -> Sale:
    """Complete a cashier sale after the manager confirms it."""
    if sale.status != 'pending_approval':
        raise ValidationError('This sale is not waiting for approval.')
    pending = pending_sale_complete_change(sale)
    payload = dict(pending.apply_payload or {}) if pending else {}
    if notify_customer is not None:
        payload['notify_customer'] = bool(notify_customer)
    complete_queued_sale(sale, user, payload)
    sale.refresh_from_db()
    notify_cashier_sale_approved(sale, user)
    from daily_notes.approval_notice import SOURCE_SALE_COMPLETE, complete_manager_queue_notes

    complete_manager_queue_notes(source=SOURCE_SALE_COMPLETE, record_id=sale.pk)
    return sale


def complete_queued_sale(sale: Sale, user, payload: dict | None = None) -> Sale:
    """Re-check stock, move inventory, apply payment, post the journal."""
    if sale.status not in ('pending_approval', 'awaiting_payment'):
        raise ValidationError(COMPLETE_NOT_READY)

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
    if customer is not None:
        customer.refresh_from_db()
    amount_paid = Decimal(str(payload.get('amount_paid', sale.amount_paid or 0)))
    use_wallet = bool(payload.get('use_wallet'))
    wallet_requested = Decimal(str(payload.get('wallet_amount') or 0))
    if 'wallet_amount_locked' in payload:
        locked = Decimal(str(payload.get('wallet_amount_locked') or 0))
        use_wallet = use_wallet and locked > 0
        wallet_requested = locked
        if use_wallet and customer is not None and customer.wallet_balance < locked:
            raise ValidationError(
                WALLET_CHANGED_MESSAGE.format(
                    customer=customer.name or 'This customer',
                    balance=customer.wallet_balance,
                    locked=locked,
                )
            )
    payment_result = service._prepare_sale_payment(
        customer=customer,
        sale_type=payload.get('sale_type') or sale.sale_type or 'pos',
        total=sale.total,
        amount_paid=amount_paid,
        allow_partial=bool(payload.get('allow_partial')),
        excess_payment_choice=payload.get('excess_payment_choice') or 'change',
        use_wallet=use_wallet,
        wallet_amount_requested=wallet_requested,
    )

    # Drain stock against existing sale lines (prices already locked at checkout).
    # Always refresh unit_cost from the validated FIFO plan when available so
    # qty/line corrections after admin return stamp accurate COGS on re-approve.
    for sale_item in sale.items.select_related('product', 'variant'):
        if not sale_item.product.track_stock:
            continue
        matched = next(
            (
                row for row in validated_items
                if row['product'].id == sale_item.product_id
                and (
                    (row['variant'].id if row['variant'] else None)
                    == sale_item.variant_id
                )
                and int(row['quantity']) == int(sale_item.quantity)
                and row['unit_price'] == sale_item.unit_price
            ),
            None,
        )
        unit_cost = sale_item.unit_cost
        missing_stamp = unit_cost is None or Decimal(str(unit_cost)) <= 0
        if matched is not None:
            unit_cost = matched['unit_cost']
        elif missing_stamp:
            unit_cost = sellable_unit_cost(sale_item.product, sale_item.variant)
        if unit_cost != sale_item.unit_cost:
            SaleItem.objects.filter(pk=sale_item.pk).update(unit_cost=unit_cost)
            sale_item.unit_cost = unit_cost
        service._create_sale_stock_movements(
            branch=sale.branch,
            user=user,
            reference=sale.sale_number,
            notes=f'Sale {sale.sale_number}',
            product=sale_item.product,
            variant=sale_item.variant,
            quantity=sale_item.quantity,
            unit_cost=unit_cost,
            sale_item=sale_item,
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

    # Posted corrections already texted the customer on first completion —
    # only re-SMS when the approver explicitly opts in.
    if sale_was_returned_from_completed(sale):
        notify_customer = payload_requests_customer_sms(payload)
    else:
        notify_customer = True
    service._apply_sale_payment(
        customer, sale, user, payment_result, notify_customer=notify_customer,
    )

    invoice_data = _invoice_validated_data(sale, payload)
    if invoice_data is not None:
        service._maybe_create_invoice_for_sale(
            sale, invoice_data, customer, user, amount_paid,
        )

    try:
        from accounting.services import create_sale_journal_entry

        create_sale_journal_entry(sale)
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            'Error creating journal entry for approved sale %s', sale.sale_number
        )

    from daily_notes.approval_notice import complete_sale_approved_notices

    complete_sale_approved_notices(sale=sale)
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
