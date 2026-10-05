"""Keep customer wallet debt aligned with completed POS sale unpaid balances.

Correction used to reverse the wallet but leave the old ``source_type='debt'``
row in place, so re-completion skipped posting the new unpaid amount. Forward
fix invalidates those rows on return. This module repairs sales already stuck.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from sales.models import CustomerWalletTransaction, Sale


def sale_unpaid_balance(sale: Sale) -> Decimal:
    total = Decimal(str(sale.total or 0))
    paid = Decimal(str(sale.amount_paid or 0))
    unpaid = total - paid
    return unpaid if unpaid > 0 else Decimal('0')


def active_sale_debt_amount(sale: Sale) -> Decimal:
    return (
        CustomerWalletTransaction.objects.filter(
            sale=sale,
            source_type='debt',
            transaction_type='debit',
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0')
    )


def _invalidate_active_debt_rows(sale: Sale, *, reason: str) -> int:
    count = 0
    for txn in CustomerWalletTransaction.objects.filter(sale=sale, source_type='debt'):
        marker = f'[SUPERSEDED] {reason}'.strip()
        prior = (txn.notes or '').strip()
        txn.source_type = 'other'
        txn.notes = f'{prior} {marker}'.strip() if prior else marker
        txn.save(update_fields=['source_type', 'notes'])
        count += 1
    return count


def debt_already_cleared_from_wallet(sale: Sale) -> bool:
    """True when a correction reverse undid debt but an older debt row is still 'active'."""
    latest_debt = (
        CustomerWalletTransaction.objects.filter(
            sale=sale,
            source_type='debt',
            transaction_type='debit',
        )
        .order_by('-id')
        .first()
    )
    if latest_debt is None:
        return False
    latest_reverse = (
        CustomerWalletTransaction.objects.filter(
            sale=sale,
            source_type='other',
            transaction_type='credit',
            id__gt=latest_debt.id,
        )
        .filter(notes__icontains='for correction')
        .order_by('-id')
        .first()
    )
    return latest_reverse is not None


@transaction.atomic
def sync_sale_customer_debt(
    sale: Sale,
    *,
    user=None,
    reason: str = 'Debt sync after sale correction',
) -> dict:
    """
    Make active debt for this sale match its unpaid balance and adjust wallet.

    Handles the post-correction bug where the wallet was reversed but a stale
    ``source_type='debt'`` row remained (so re-complete skipped a new debt).
    """
    sale = Sale.objects.select_related('customer').get(pk=sale.pk)
    customer = sale.customer
    unpaid = sale_unpaid_balance(sale)
    active = active_sale_debt_amount(sale)

    result = {
        'sale_id': sale.pk,
        'sale_number': sale.sale_number,
        'unpaid': unpaid,
        'active_debt_before': active,
        'wallet_before': customer.wallet_balance if customer else None,
        'adjusted': Decimal('0'),
        'action': 'noop',
    }

    if customer is None:
        result['action'] = 'no_customer'
        return result
    if sale.status != 'completed':
        result['action'] = 'not_completed'
        return result
    if getattr(sale, 'sale_type', 'pos') == 'normal':
        result['action'] = 'invoice_sale'
        return result
    if unpaid == active and not debt_already_cleared_from_wallet(sale):
        result['action'] = 'already_synced'
        return result

    customer.refresh_from_db()
    result['wallet_before'] = customer.wallet_balance
    stale_on_ledger_only = debt_already_cleared_from_wallet(sale)

    if active > 0:
        _invalidate_active_debt_rows(sale, reason=reason)
        if not stale_on_ledger_only:
            # Debt is still on the wallet — undo it before posting the new unpaid.
            customer.wallet_balance += active
            customer.save(update_fields=['wallet_balance', 'updated_at'])
            CustomerWalletTransaction.objects.create(
                customer=customer,
                transaction_type='credit',
                source_type='other',
                amount=active,
                balance_after=customer.wallet_balance,
                sale=sale,
                reference=sale.sale_number,
                notes=f'{reason} (cleared active debt {active})',
                created_by=user,
            )

    if unpaid > 0:
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
            notes=reason,
            created_by=user,
        )
        result['action'] = 'debt_synced'
        result['adjusted'] = unpaid if stale_on_ledger_only else (unpaid - active)
    else:
        result['action'] = 'debt_cleared'
        result['adjusted'] = Decimal('0') if stale_on_ledger_only else -active

    customer.refresh_from_db()
    result['wallet_after'] = customer.wallet_balance
    result['active_debt_after'] = active_sale_debt_amount(sale)
    return result
