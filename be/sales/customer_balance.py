"""
Balance filters for the customer list.

``wallet_debt`` keeps customers whose wallet is negative. ``wallet_credit``
keeps customers whose wallet is positive — money the shop is holding for
them. ``invoice`` keeps customers whose invoice balance is above zero.
Counts are taken before the filter so the summary cards stay store-wide
while the table shows the match.
Money figures are quantised to 0.01. Counts are non-negative integers.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Case, Count, DecimalField, F, Q, Sum, Value, When

BALANCE_WALLET = 'wallet_debt'
BALANCE_CREDIT = 'wallet_credit'
BALANCE_INVOICE = 'invoice'
_MONEY = DecimalField(max_digits=14, decimal_places=2)


def normalize_balance_filter(
    value: str | None,
    *,
    wallet_visible: bool = True,
    invoice_visible: bool = True,
) -> str:
    """
    Accept only a balance filter the store is allowed to show.

    Args:
        value: Raw query value. Blank, unknown, or longer than 32 characters
            becomes an empty filter. Expected values are ``wallet_debt``,
            ``wallet_credit``, and ``invoice``.
        wallet_visible: When False, both wallet filters are dropped so a
            hidden wallet cannot be queried.
        invoice_visible: When False, ``invoice`` is dropped.

    Returns:
        str: ``wallet_debt``, ``wallet_credit``, ``invoice``, or ``''``.
        Never raises.
    """
    key = (value or '').strip()
    if len(key) > 32:
        return ''
    if key in (BALANCE_WALLET, BALANCE_CREDIT) and wallet_visible:
        return key
    if key == BALANCE_INVOICE and invoice_visible:
        return BALANCE_INVOICE
    return ''


def apply_customer_balance_filter(queryset, balance: str):
    """
    Narrow a customer queryset to one balance kind.

    Args:
        queryset: Customer queryset. For ``invoice`` it must already be
            annotated with ``annotated_outstanding`` (sum of invoice
            balances, null when the customer has no invoices).
        balance: ``wallet_debt``, ``wallet_credit``, ``invoice``, or
            anything else. Anything else returns the queryset unchanged.

    Returns:
        Queryset: Filtered copy, or the same queryset when ``balance`` is
        empty. No writes.

    Raises:
        None. An unknown balance is ignored.
    """
    if balance == BALANCE_WALLET:
        return queryset.filter(wallet_balance__lt=0)
    if balance == BALANCE_CREDIT:
        return queryset.filter(wallet_balance__gt=0)
    if balance == BALANCE_INVOICE:
        return queryset.filter(annotated_outstanding__gt=0)
    return queryset


def _money(value) -> str:
    """
    Format an aggregate as a 2-decimal string.

    Args:
        value: Number, Decimal, or None. None is treated as zero.

    Returns:
        str: Quantised amount, for example ``14900.00``. No thousands
        separator. Absolute value is not applied here.
    """
    amount = Decimal(value or 0).quantize(Decimal('0.01'))
    return format(amount, 'f')


def customer_balance_summary(
    queryset,
    *,
    include_wallet: bool = True,
    include_invoice: bool = True,
) -> dict:
    """
    Count customers and the money behind the summary cards.

    Args:
        queryset: Customers already limited by search, location, and
            visibility, and annotated with ``annotated_outstanding``.
            Do not apply the balance filter before this call.
        include_wallet: When False, wallet debt and credit figures are
            zero so a hidden wallet is not reported.
        include_invoice: When False, invoice counts and the outstanding
            total are zero.

    Returns:
        dict: ``count`` (0+), ``with_invoice`` (0+), ``invoice_outstanding``
        (string, 0.00 and up), ``with_wallet_debt`` (0+),
        ``total_wallet_debt`` (string, absolute value of negative wallets),
        ``with_wallet_credit`` (0+), ``total_wallet_credit`` (string, sum of
        positive wallets — money the shop is holding). One aggregate query.
        No writes.

    Raises:
        None. A queryset without the annotation yields zero invoice totals
        if the database rejects the field; callers must annotate first.
    """
    wallet_debt = Case(
        When(wallet_balance__lt=0, then=-F('wallet_balance')),
        default=Value(Decimal('0.00')),
        output_field=_MONEY,
    )
    wallet_credit = Case(
        When(wallet_balance__gt=0, then=F('wallet_balance')),
        default=Value(Decimal('0.00')),
        output_field=_MONEY,
    )
    aggregated = queryset.aggregate(
        count=Count('id'),
        with_invoice=Count('id', filter=Q(annotated_outstanding__gt=0)),
        invoice_outstanding=Sum(
            'annotated_outstanding',
            filter=Q(annotated_outstanding__gt=0),
        ),
        with_wallet_debt=Count('id', filter=Q(wallet_balance__lt=0)),
        total_wallet_debt=Sum(wallet_debt),
        with_wallet_credit=Count('id', filter=Q(wallet_balance__gt=0)),
        total_wallet_credit=Sum(wallet_credit),
    )
    show_wallet = include_wallet
    return {
        'count': int(aggregated['count'] or 0),
        'with_invoice': int(aggregated['with_invoice'] or 0) if include_invoice else 0,
        'invoice_outstanding': _money(aggregated['invoice_outstanding']) if include_invoice else '0.00',
        'with_wallet_debt': int(aggregated['with_wallet_debt'] or 0) if show_wallet else 0,
        'total_wallet_debt': _money(aggregated['total_wallet_debt']) if show_wallet else '0.00',
        'with_wallet_credit': int(aggregated['with_wallet_credit'] or 0) if show_wallet else 0,
        'total_wallet_credit': _money(aggregated['total_wallet_credit']) if show_wallet else '0.00',
    }
