"""
Admin-only correction of posted debt collection (cash collected) amounts.

Reverses FIFO sale allocations, adjusts the wallet credit, then re-applies
allocations for the new amount. Audited separately from posting.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from sales.models import CustomerWalletTransaction, DebtSettlementAllocation
from sales.sale_debt_sync import apply_settlement_to_underpaid_sales


def _money(value) -> Decimal:
    """Quantize to 0.01 money; None/blank → 0.00."""
    try:
        return Decimal(str(value or 0)).quantize(Decimal('0.01'))
    except Exception:
        return Decimal('0.00')


@transaction.atomic
def reverse_settlement_allocations(wallet_txn: CustomerWalletTransaction) -> Decimal:
    """
    Undo FIFO ``amount_paid`` bumps for one settlement and delete allocation rows.

    Args:
        wallet_txn: Posted ``debt_settlement`` credit transaction.

    Returns:
        Total allocation amount reversed (non-negative Decimal, 0.01 steps).
    """
    total = Decimal('0.00')
    rows = list(
        DebtSettlementAllocation.objects.filter(
            wallet_transaction=wallet_txn
        ).select_related('sale')
    )
    for alloc in rows:
        chunk = _money(alloc.amount)
        sale = alloc.sale
        paid = _money(sale.amount_paid)
        sale.amount_paid = max(Decimal('0.00'), paid - chunk)
        sale.save(update_fields=['amount_paid', 'updated_at'])
        total += chunk
    if rows:
        DebtSettlementAllocation.objects.filter(
            wallet_transaction=wallet_txn
        ).delete()
    return total.quantize(Decimal('0.01'))


@transaction.atomic
def correct_debt_settlement_amount(
    *,
    txn_id: int,
    new_amount,
    user=None,
    reason: str = '',
) -> CustomerWalletTransaction:
    """
    Change the cash collected on a posted debt settlement (admin correction).

    Args:
        txn_id: Primary key of a credit ``debt_settlement`` wallet transaction.
        new_amount: Replacement amount; must be >= 0.01 and differ from current.
        user: Actor (stored in notes only; audit logs separately).
        reason: Optional short note appended to the transaction (max ~200 chars used).

    Returns:
        Updated ``CustomerWalletTransaction`` with refreshed customer FK.

    Raises:
        CustomerWalletTransaction.DoesNotExist: Unknown txn id.
        ValidationError: Wrong type, invalid amount, or no change.
    """
    txn = (
        CustomerWalletTransaction.objects.select_related('customer')
        .select_for_update()
        .get(pk=txn_id)
    )
    if txn.source_type != 'debt_settlement' or txn.transaction_type != 'credit':
        raise ValidationError(
            'Only posted debt collection (settlement credit) rows can be corrected.'
        )

    old_amount = _money(txn.amount)
    amount = _money(new_amount)
    if amount < Decimal('0.01'):
        raise ValidationError('Corrected amount must be at least 0.01.')
    if amount == old_amount:
        raise ValidationError('New amount is the same as the current amount.')

    customer = txn.customer
    reverse_settlement_allocations(txn)

    delta = amount - old_amount
    customer.wallet_balance = _money(customer.wallet_balance) + delta
    customer.save(update_fields=['wallet_balance', 'updated_at'])

    note_bits = [
        (txn.notes or '').strip(),
        f'Admin corrected amount {old_amount} → {amount}',
    ]
    if user is not None:
        uname = getattr(user, 'username', None) or getattr(user, 'pk', '')
        note_bits[-1] = f'{note_bits[-1]} by {uname}'
    reason_clean = (reason or '').strip()[:200]
    if reason_clean:
        note_bits.append(f'Reason: {reason_clean}')
    txn.amount = amount
    txn.balance_after = _money(customer.wallet_balance)
    txn.notes = ' · '.join(bit for bit in note_bits if bit)[:2000]
    txn.save(update_fields=['amount', 'balance_after', 'notes'])

    apply_settlement_to_underpaid_sales(customer, amount, wallet_txn=txn)
    txn.refresh_from_db()
    return txn
