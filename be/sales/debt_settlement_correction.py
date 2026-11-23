"""
Admin-only correction of posted debt collections.

Amount edits reverse FIFO sale allocations, adjust the wallet credit, then
re-apply the new amount. Customer transfers move that same credit, and
optionally the sales it paid, onto the customer who actually paid.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from sales.models import Customer, CustomerWalletTransaction, DebtSettlementAllocation, Sale
from sales.sale_debt_sync import (
    apply_settlement_to_underpaid_sales,
    rebuild_customer_wallet_from_active_ledger,
)


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


def _customer_label(customer: Customer) -> str:
    """Name for notes. Never includes a phone number. Blank name → 'Customer'."""
    name = (getattr(customer, 'name', None) or '').strip()
    return name[:120] or 'Customer'


@transaction.atomic
def transfer_debt_settlement_customer(
    *,
    txn_id: int,
    target_customer_id: int,
    user=None,
    reason: str = '',
    move_sales: bool = False,
) -> dict:
    """
    Move a posted debt repayment from the wrong customer to the right one.

    The credit leaves the original wallet. When ``move_sales`` is false, the
    sales that were marked paid go back to unpaid and the money is applied to
    the target customer's open debt. When true, those sales (and their debt
    rows) move with the repayment and stay paid.

    Args:
        txn_id: Primary key of a credit ``debt_settlement`` row, 1–2^31-1.
        target_customer_id: Active customer who should hold the money, 1–2^31-1.
        user: Actor, stored in the note only. None omits the username.
        reason: Optional note, 0–200 characters. Blank is allowed.
        move_sales: When true, also change ``Sale.customer`` for sales this
            repayment paid. False leaves those sales on the original customer.

    Returns:
        Dict with ``transaction``, ``from_customer``, ``to_customer``, and
        ``moved_sale_ids`` (0–50 sale ids). Wallet balances are rebuilt.

    Raises:
        CustomerWalletTransaction.DoesNotExist: Unknown txn id.
        ValidationError: Not a repayment, same customer, inactive target,
            or a sale that was also paid by a different repayment.
    """
    txn = (
        CustomerWalletTransaction.objects.select_related('customer')
        .select_for_update()
        .get(pk=txn_id)
    )
    if txn.source_type != 'debt_settlement' or txn.transaction_type != 'credit':
        raise ValidationError('Only a posted debt repayment can be moved.')

    try:
        target_id = int(target_customer_id)
    except (TypeError, ValueError):
        raise ValidationError('Choose a customer.')
    if target_id < 1:
        raise ValidationError('Choose a customer.')
    if int(txn.customer_id or 0) == target_id:
        raise ValidationError('That repayment is already on this customer.')

    old_id = int(txn.customer_id)
    locked_ids = sorted({old_id, target_id})
    locked = {
        row.pk: row
        for row in Customer.objects.select_for_update().filter(pk__in=locked_ids)
    }
    old = locked.get(old_id)
    target = locked.get(target_id)
    if old is None:
        raise ValidationError('The customer on this repayment no longer exists.')
    if target is None or not target.is_active:
        raise ValidationError('Choose an active customer.')

    sale_ids = list(
        DebtSettlementAllocation.objects.filter(wallet_transaction=txn)
        .order_by('id')
        .values_list('sale_id', flat=True)
    )
    if txn.sale_id and txn.sale_id not in sale_ids:
        sale_ids.append(txn.sale_id)
    sale_ids = [int(sid) for sid in sale_ids if sid]
    if len(sale_ids) > 50:
        raise ValidationError('This repayment is tied to too many sales to move at once.')

    moved_sale_ids: list[int] = []
    if move_sales and sale_ids:
        other = DebtSettlementAllocation.objects.filter(
            sale_id__in=sale_ids,
        ).exclude(wallet_transaction=txn)
        if other.exists():
            raise ValidationError(
                'A sale on this repayment was also paid by another repayment. '
                'Move only the repayment, without the sales.'
            )
        Sale.objects.filter(pk__in=sale_ids).update(customer_id=target.pk)
        CustomerWalletTransaction.objects.filter(
            sale_id__in=sale_ids,
        ).exclude(pk=txn.pk).update(customer_id=target.pk)
        moved_sale_ids = list(sale_ids)
    else:
        reverse_settlement_allocations(txn)

    actor = ''
    if user is not None:
        actor = str(getattr(user, 'username', None) or getattr(user, 'pk', '') or '')[:150]
    note_bits = [
        (txn.notes or '').strip(),
        (
            f"Moved from {_customer_label(old)} to {_customer_label(target)}"
            + (f' by {actor}' if actor else '')
        ),
    ]
    if moved_sale_ids:
        note_bits.append(f'Sales moved: {len(moved_sale_ids)}')
    reason_clean = (reason or '').strip()[:200]
    if reason_clean:
        note_bits.append(f'Reason: {reason_clean}')
    txn.customer = target
    txn.notes = ' · '.join(bit for bit in note_bits if bit)[:2000]
    txn.save(update_fields=['customer', 'notes'])

    rebuild_customer_wallet_from_active_ledger(old.pk)
    rebuild_customer_wallet_from_active_ledger(target.pk)
    if not move_sales:
        apply_settlement_to_underpaid_sales(target, txn.amount, wallet_txn=txn)

    txn.refresh_from_db()
    old.refresh_from_db()
    target.refresh_from_db()
    return {
        'transaction': txn,
        'from_customer': old,
        'to_customer': target,
        'moved_sale_ids': moved_sale_ids,
    }
