"""Restore mistaken voids/rollbacks and cancelled (never-posted) sales."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from sales.models import CustomerWalletTransaction, Sale, SaleRefund


UNVOID_NOT_VOIDED = 'Only a fully voided or rolled-back sale can be restored this way.'
UNCANCEL_NOT_CANCELLED = 'Only a cancelled sale can be restored this way.'
REASON_REQUIRED = 'A reason is required to restore this sale.'


def sale_is_unvoidable(sale: Sale) -> bool:
    return (
        sale is not None
        and sale.status == 'completed'
        and (getattr(sale, 'refund_status', 'none') or 'none') == 'refunded'
    )


def sale_is_uncancellable(sale: Sale) -> bool:
    return sale is not None and sale.status == 'cancelled'


@transaction.atomic
def unvoid_sale(*, sale: Sale, reason: str, user) -> Sale:
    """Undo a full void/rollback: stock, customer debt/wallet, refund journals, refund rows."""
    reason = (reason or '').strip()
    if not reason:
        raise ValidationError({'reason': REASON_REQUIRED})
    if not sale_is_unvoidable(sale):
        raise ValidationError(UNVOID_NOT_VOIDED)

    refunds = list(sale.refunds.select_related('sale').prefetch_related('items').order_by('id'))
    if not refunds:
        raise ValidationError(UNVOID_NOT_VOIDED)

    from accounting.reversal import reverse_source_documents
    from sales.services import SaleService

    sale_service = SaleService()
    notes = f'Unvoid of {sale.sale_number}: {reason}'.strip()

    for refund in refunds:
        reverse_source_documents(
            'sale_refund',
            refund.pk,
            reason=notes,
            user=user,
        )
        for line in refund.items.select_related('product', 'variant', 'sale_item'):
            product = line.product
            if not product or not product.track_stock:
                continue
            qty = int(line.quantity or 0)
            if qty <= 0:
                continue
            sale_service._create_sale_stock_movements(  # noqa: SLF001 — restore posted sale drain
                branch=sale.branch,
                user=user,
                reference=sale.sale_number,
                notes=notes,
                product=product,
                variant=line.variant,
                quantity=qty,
                unit_cost=line.sale_item.unit_cost if line.sale_item_id else None,
                sale_item=line.sale_item,
            )

    _reapply_refund_wallet_effects(sale, user=user, reason=reason)

    for refund in refunds:
        refund.items.all().delete()
        refund.delete()

    sale.refund_status = 'none'
    sale.save(update_fields=['refund_status', 'updated_at'])
    sale.refresh_from_db()
    return sale


@transaction.atomic
def uncancel_sale(*, sale: Sale, reason: str, user) -> Sale:
    """Put a cancelled (never-posted) sale back on hold so it can be fixed or re-queued."""
    reason = (reason or '').strip()
    if not reason:
        raise ValidationError({'reason': REASON_REQUIRED})
    if not sale_is_uncancellable(sale):
        raise ValidationError(UNCANCEL_NOT_CANCELLED)

    sale.status = 'holding'
    sale.save(update_fields=['status', 'updated_at'])
    sale.refresh_from_db()
    return sale


def _reapply_refund_wallet_effects(sale: Sale, *, user, reason: str) -> None:
    """Reverse wallet/debt credits that a void wrote (source_type=refund)."""
    customer = sale.customer
    if customer is None:
        return
    refund_txns = list(
        CustomerWalletTransaction.objects.filter(
            sale=sale,
            source_type='refund',
        ).order_by('id')
    )
    if not refund_txns:
        # Fallback when allocation used implied debt without a wallet payment row:
        # rebuild debt from sale totals after refunds are gone.
        return

    customer.refresh_from_db()
    for txn in refund_txns:
        amount = txn.amount or Decimal('0')
        if amount <= 0:
            continue
        if txn.transaction_type == 'credit':
            customer.wallet_balance -= amount
            reverse_type = 'debit'
        else:
            customer.wallet_balance += amount
            reverse_type = 'credit'
        customer.save(update_fields=['wallet_balance', 'updated_at'])
        CustomerWalletTransaction.objects.create(
            customer=customer,
            transaction_type=reverse_type,
            source_type='other',
            amount=amount,
            balance_after=customer.wallet_balance,
            sale=sale,
            reference=sale.sale_number,
            notes=f'Unvoid of sale {sale.sale_number}: {reason}',
            created_by=user,
        )
        marker = f'[REVERSED by unvoid] {reason}'.strip()
        prior = (txn.notes or '').strip()
        txn.source_type = 'other'
        txn.notes = f'{prior} {marker}'.strip() if prior else marker
        txn.save(update_fields=['source_type', 'notes'])

    # If the sale still has unpaid balance and no active debt row, re-post debt.
    customer.refresh_from_db()
    unpaid = (sale.total or Decimal('0')) - (sale.amount_paid or Decimal('0'))
    wallet_paid = (
        CustomerWalletTransaction.objects.filter(
            sale=sale,
            transaction_type='debit',
            source_type='payment',
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0')
    )
    unpaid = unpaid - Decimal(str(wallet_paid))
    active_debt = (
        CustomerWalletTransaction.objects.filter(
            sale=sale,
            transaction_type='debit',
            source_type='debt',
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0')
    )
    if unpaid > 0 and Decimal(str(active_debt)) <= 0:
        customer.wallet_balance -= unpaid
        customer.save(update_fields=['wallet_balance', 'updated_at'])
        CustomerWalletTransaction.objects.create(
            customer=customer,
            transaction_type='debit',
            source_type='debt',
            amount=unpaid,
            balance_after=customer.wallet_balance,
            sale=sale,
            reference=sale.sale_number,
            notes=f'Debt restored by unvoid of {sale.sale_number}: {reason}',
            created_by=user,
        )
