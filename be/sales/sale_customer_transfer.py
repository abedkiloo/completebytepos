"""
Move one completed sale onto the customer it was actually for.

The sale, its invoice, and its own debt row move. A later debt repayment
that had been applied to the sale stays on the customer it was keyed to
and is applied to that customer's remaining debt.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from sales.debt_settlement_correction import _customer_label, _money
from sales.models import Customer, CustomerWalletTransaction, DebtSettlementAllocation, Invoice, Sale
from sales.sale_debt_sync import (
    active_sale_debt_amount,
    apply_settlement_to_underpaid_sales,
    rebuild_customer_wallet_from_active_ledger,
    sale_unpaid_balance,
    sync_sale_customer_debt,
)


def _release_settlements_on_sale(sale: Sale) -> list[tuple[CustomerWalletTransaction, Decimal]]:
    """
    Take later debt-repayment chunks off this sale only.

    Checkout cash on ``amount_paid`` stays. The repayment credit stays on
    the customer it was keyed to.

    Args:
        sale: Completed sale whose ``amount_paid`` may include settlements.

    Returns:
        Pairs of (settlement credit, amount freed). One pair per allocation
        on the sale, 0–200. Each amount is 0.01 up to that allocation, and
        the total freed is never more than ``amount_paid``.

    Raises:
        ValidationError: More than 200 repayment chunks are on this one sale.
    """
    rows = list(
        DebtSettlementAllocation.objects.filter(sale=sale)
        .select_related('wallet_transaction')
        .order_by('id')
    )
    if len(rows) > 200:
        raise ValidationError('This sale has too many repayments to move at once.')
    if not rows:
        return []
    paid = _money(sale.amount_paid)
    freed: list[tuple[CustomerWalletTransaction, Decimal]] = []
    for alloc in rows:
        chunk = min(_money(alloc.amount), paid)
        if chunk <= 0:
            continue
        paid = (paid - chunk).quantize(Decimal('0.01'))
        freed.append((alloc.wallet_transaction, chunk))
    DebtSettlementAllocation.objects.filter(pk__in=[row.pk for row in rows]).delete()
    sale.amount_paid = paid
    sale.save(update_fields=['amount_paid', 'updated_at'])
    return freed


def _queue_sale_sms(sale: Sale, user, send_sms: bool) -> bool:
    """
    Text the customer who now owns the sale, when an admin asked for it.

    Args:
        sale: Sale after the customer change. Must already be saved.
        user: Actor stored on the outbox. None leaves ``created_by`` empty.
        send_sms: False skips the text. True queues one sale SMS.

    Returns:
        True when an outbox row was queued. False when skipped or the
        customer has no phone. Never includes the phone number.
    """
    if not send_sms:
        return False
    try:
        from messaging.customer_notify import notify_customer_sale_completed

        msg = notify_customer_sale_completed(sale, user=user, force_send=True)
        return msg is not None
    except Exception:
        return False


@transaction.atomic
def transfer_sale_customer(
    *,
    sale_id: int,
    target_customer_id: int,
    user=None,
    reason: str = '',
    send_sms: bool = False,
) -> dict:
    """
    Move one completed sale onto another customer.

    Stock, price, and quantity stay as they are. A repayment that had
    cleared part of this sale is not moved; it stays with the customer
    it was keyed to.

    Args:
        sale_id: Primary key of a completed sale, 1–2^31-1.
        target_customer_id: Active customer who should own the sale, 1–2^31-1.
        user: Actor, stored in the note only. None omits the username.
        reason: Optional note, 0–200 characters. Blank is allowed.
        send_sms: When True, queue one SMS to the target customer. False
            sends nothing. Default False.

    Returns:
        Dict with ``sale``, ``from_customer`` (or None), ``to_customer``,
        and ``sms_sent``. Wallet balances are rebuilt.

    Raises:
        Sale.DoesNotExist: Unknown sale id.
        ValidationError: Sale is not completed, same customer, or the
            target is missing or inactive.
    """
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if sale.status != 'completed':
        raise ValidationError('Only a completed sale can be moved to another customer.')

    try:
        target_id = int(target_customer_id)
    except (TypeError, ValueError):
        raise ValidationError('Choose a customer.')
    if target_id < 1:
        raise ValidationError('Choose a customer.')
    if int(sale.customer_id or 0) == target_id:
        raise ValidationError('That sale is already on this customer.')

    old_id = int(sale.customer_id) if sale.customer_id else None
    lock_ids = [target_id] if old_id is None else sorted({old_id, target_id})
    locked = {
        row.pk: row
        for row in Customer.objects.select_for_update().filter(pk__in=lock_ids)
    }
    old = locked.get(old_id) if old_id else None
    target = locked.get(target_id)
    if old_id and old is None:
        raise ValidationError('The customer on this sale no longer exists.')
    if target is None or not target.is_active:
        raise ValidationError('Choose an active customer.')

    freed = _release_settlements_on_sale(sale)
    CustomerWalletTransaction.objects.filter(
        sale=sale,
        source_type__in=('debt', 'payment'),
    ).update(customer_id=target.pk)

    actor = ''
    if user is not None:
        actor = str(getattr(user, 'username', None) or getattr(user, 'pk', '') or '')[:150]
    note = f"Moved from {_customer_label(old) if old else 'no customer'} to {_customer_label(target)}"
    if actor:
        note = f'{note} by {actor}'
    reason_clean = (reason or '').strip()[:200]
    if reason_clean:
        note = f'{note}. Reason: {reason_clean}'
    existing = (sale.notes or '').strip()
    sale.notes = (f'{existing}\n{note}' if existing else note)[:4000]
    sale.customer = target
    sale.save(update_fields=['customer', 'notes', 'updated_at'])

    Invoice.objects.filter(sale=sale).update(
        customer_id=target.pk,
        customer_name=(target.name or '')[:200],
        customer_email=(getattr(target, 'email', None) or '')[:254],
        customer_phone=(getattr(target, 'phone', None) or '')[:20],
        customer_address=(getattr(target, 'address', None) or '')[:2000],
    )

    if old is not None:
        rebuild_customer_wallet_from_active_ledger(old.pk)
    grouped: dict[int, tuple[CustomerWalletTransaction, Decimal]] = {}
    for txn, chunk in freed:
        current = grouped.get(txn.pk)
        if current is None:
            grouped[txn.pk] = (txn, chunk)
        else:
            grouped[txn.pk] = (current[0], current[1] + chunk)
    for txn, chunk in grouped.values():
        txn.refresh_from_db()
        if txn.customer_id:
            apply_settlement_to_underpaid_sales(txn.customer, chunk, wallet_txn=txn)

    sale.refresh_from_db()
    if active_sale_debt_amount(sale) == 0 and sale_unpaid_balance(sale) > 0:
        sync_sale_customer_debt(sale, user=user, reason='Debt moved with sale')
    rebuild_customer_wallet_from_active_ledger(target.pk)
    if old is not None:
        rebuild_customer_wallet_from_active_ledger(old.pk)

    sale.refresh_from_db()
    target.refresh_from_db()
    if old is not None:
        old.refresh_from_db()
    sms_sent = _queue_sale_sms(sale, user, send_sms)
    return {
        'sale': sale,
        'from_customer': old,
        'to_customer': target,
        'sms_sent': sms_sent,
    }
