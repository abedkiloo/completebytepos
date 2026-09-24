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
) -> PendingChange:
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
            'effect': 'Wallet credited after manager approval',
        },
        reason=collection_reason(amount=amount, payment_method=method, notes=notes),
        apply_payload={
            'amount': amount_str,
            'payment_method': method,
            'reference': reference,
            'notes': notes,
        },
        require_maker_checker=False,
    )
