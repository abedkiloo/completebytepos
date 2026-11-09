"""Queue customer debt collections for manager/admin approval before the wallet changes."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError

from approvals.models import PendingChange
from approvals.registry import ACTION_DEBT_COLLECTION
from approvals.service import submit_change
from sales.models import Customer

METHOD_LABELS = {
    'cash': 'Cash',
    'mpesa': 'M-PESA',
}


def customer_has_pending_debt_collection(customer: Customer) -> bool:
    return PendingChange.objects.filter(
        action_type=ACTION_DEBT_COLLECTION,
        entity_type='sales.Customer',
        entity_id=str(customer.pk),
        status=PendingChange.STATUS_PENDING,
    ).exists()


def collection_reason(*, amount: Decimal, payment_method: str, notes: str = '') -> str:
    notes = (notes or '').strip()
    if notes:
        return notes
    method_label = METHOD_LABELS.get(payment_method, payment_method)
    return f'Debt collection of {amount} via {method_label}'


def queue_debt_collection(
    request,
    customer: Customer,
    *,
    amount: Decimal,
    payment_method: str,
    reference: str = '',
    notes: str = '',
    payer_name: str = '',
    payer_phone: str = '',
    mpesa_destination: str = '',
) -> PendingChange:
    """
    Queue a debt collection for manager approval.

    Args:
        request: HTTP request (maker identity).
        customer: Customer whose wallet will be credited on approve.
        amount: Positive payment amount (KES, > 0).
        payment_method: ``cash`` or ``mpesa``.
        reference: Optional M-Pesa / receipt code (≤ 100 chars).
        notes: Optional free-text note.
        payer_name: Who paid (≤ 120 chars).
        payer_phone: Payer phone (≤ 32 chars).
        mpesa_destination: ``till``, ``bank``, or blank.

    Returns:
        PendingChange awaiting checker approval.

    Raises:
        ValidationError: Amount ≤ 0 or another collection already pending.
    """
    if amount <= 0:
        raise ValidationError('Payment amount must be greater than zero.')
    if customer_has_pending_debt_collection(customer):
        raise ValidationError(
            'A debt collection for this customer is already awaiting manager approval. '
            'Approve or reject it before submitting another.'
        )

    method = payment_method or 'cash'
    reference = (reference or '').strip()
    notes = (notes or '').strip()
    payer_name = (payer_name or '').strip()[:120]
    payer_phone = (payer_phone or '').strip()[:32]
    mpesa_destination = (mpesa_destination or '').strip().lower()[:16]
    amount_str = str(amount)

    return submit_change(
        request=request,
        action_type=ACTION_DEBT_COLLECTION,
        entity_type='sales.Customer',
        entity_id=customer.pk,
        entity_repr=str(customer.name or customer.pk),
        original_values={
            'wallet_balance': str(customer.wallet_balance),
        },
        proposed_values={
            'amount': amount_str,
            'payment_method': method,
            'reference': reference,
            'payer_name': payer_name,
            'payer_phone': payer_phone,
            'mpesa_destination': mpesa_destination,
            'effect': 'Wallet credited after manager approval',
        },
        reason=collection_reason(amount=amount, payment_method=method, notes=notes),
        apply_payload={
            'amount': amount_str,
            'payment_method': method,
            'reference': reference,
            'notes': notes,
            'payer_name': payer_name,
            'payer_phone': payer_phone,
            'mpesa_destination': mpesa_destination,
        },
        require_maker_checker=False,
    )
