"""Split a refund amount across cash, wallet, and customer-account (debt) portions."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict

from django.db.models import Sum

from sales.models import Sale


def _sale_wallet_component(sale: Sale, source_type: str) -> Decimal:
    if not getattr(sale, 'pk', None):
        return Decimal('0')
    from sales.models import CustomerWalletTransaction

    total = (
        CustomerWalletTransaction.objects.filter(
            sale=sale,
            transaction_type='debit',
            source_type=source_type,
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0')
    )
    return Decimal(str(total))


def compute_refund_allocation(sale: Sale, refund_amount: Decimal) -> Dict[str, Decimal]:
    """
    Map refund_amount to the economic components that must be reversed:
      - cash_back: physical / M-Pesa cash returned to customer
      - wallet_back: prepaid wallet balance restored
      - debt_back: customer account balance (unpaid sale debt) reduced
    """
    refund_amount = Decimal(str(refund_amount or 0))
    if refund_amount <= 0:
        return {
            'cash_back': Decimal('0'),
            'wallet_back': Decimal('0'),
            'debt_back': Decimal('0'),
        }

    total = sale.total or Decimal('0')
    ratio = min(Decimal('1'), refund_amount / total) if total > 0 else Decimal('1')

    cash_paid = sale.amount_paid or Decimal('0')
    wallet_used = _sale_wallet_component(sale, 'payment')
    debt_recorded = _sale_wallet_component(sale, 'debt')
    if debt_recorded <= 0 and total > 0:
        implied_debt = total - cash_paid - wallet_used
        if implied_debt > 0:
            debt_recorded = implied_debt

    cash_back = (cash_paid * ratio).quantize(Decimal('0.01'))
    wallet_back = (wallet_used * ratio).quantize(Decimal('0.01'))
    debt_back = (debt_recorded * ratio).quantize(Decimal('0.01'))

    allocated = cash_back + wallet_back + debt_back
    remainder = (refund_amount - allocated).quantize(Decimal('0.01'))
    if remainder > 0:
        if debt_recorded > 0:
            debt_back += remainder
        elif wallet_used > 0:
            wallet_back += remainder
        elif cash_paid > 0:
            cash_back += remainder
        else:
            debt_back += remainder

    return {
        'cash_back': max(Decimal('0'), cash_back),
        'wallet_back': max(Decimal('0'), wallet_back),
        'debt_back': max(Decimal('0'), debt_back),
    }
