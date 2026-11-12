"""Normalize and label sale tender methods (cash / M-Pesa / pay later)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

SALE_PAYMENT_METHOD_CHOICES = (
    ('cash', 'Cash'),
    ('mpesa', 'M-PESA'),
    ('on_account', 'Pay later'),
    ('card', 'Card'),
    ('other', 'Other'),
)

SALE_PAYMENT_METHOD_VALUES = frozenset(c[0] for c in SALE_PAYMENT_METHOD_CHOICES)

MPESA_DESTINATION_CHOICES = (
    ('', '—'),
    ('till', 'Till'),
    ('bank', 'Bank'),
)


def as_decimal(value: Any) -> Decimal:
    """Parse money-like input to Decimal; invalid / empty → 0."""
    try:
        return Decimal(str(value if value is not None else 0))
    except Exception:
        return Decimal('0')


def normalize_sale_payment_method(
    *,
    payment_method: str | None,
    amount_paid: Any = 0,
    allow_partial: bool = False,
) -> str:
    """
    Choose the stored sale tender code.

    Pay-later / zero tender with on-account must never stay as ``cash``.
    When collecting now, keep cash/mpesa; blank → cash.

    Args:
        payment_method: Requested tender (cash / mpesa / on_account / …).
        amount_paid: Amount collected now (0 allowed for pay later).
        allow_partial: True when balance may sit on the customer account.

    Returns:
        One of ``SALE_PAYMENT_METHOD_VALUES`` (defaults to ``cash``).
    """
    paid = as_decimal(amount_paid)
    method = (payment_method or '').strip().lower()
    if paid <= 0 and allow_partial:
        return 'on_account'
    if method in SALE_PAYMENT_METHOD_VALUES:
        return method
    return 'cash'


def sale_payment_method_label(
    payment_method: str | None,
    *,
    amount_paid: Any = None,
    total: Any = None,
    mpesa_destination: str | None = '',
) -> str:
    """
    Cashier-facing tender label for history / detail / receipts.

    Unpaid sales (amount_paid ≈ 0 with balance due, or ``on_account``) →
    ``Pay later``. M-Pesa with till/bank appends the destination.

    Args:
        payment_method: Stored tender code.
        amount_paid: Collected amount (optional; used for legacy cash+0 rows).
        total: Sale total (optional; with amount_paid detects unpaid).
        mpesa_destination: ``till`` / ``bank`` / blank.

    Returns:
        Short display string (never empty).
    """
    method = (payment_method or '').strip().lower()
    paid = as_decimal(amount_paid) if amount_paid is not None else None
    tot = as_decimal(total) if total is not None else None

    unpaid = method == 'on_account'
    if not unpaid and paid is not None and tot is not None and tot > 0 and paid <= 0:
        unpaid = True
    elif not unpaid and paid is not None and paid <= 0 and method in ('', 'cash'):
        # Legacy rows: cash + 0 paid without total in context → still pay later.
        if tot is None or tot > 0:
            unpaid = True

    if unpaid:
        return 'Pay later'

    if method == 'mpesa':
        dest = (mpesa_destination or '').strip().lower()
        if dest == 'till':
            return 'M-Pesa · Till'
        if dest == 'bank':
            return 'M-Pesa · Bank'
        return 'M-Pesa'

    labels = dict(SALE_PAYMENT_METHOD_CHOICES)
    return labels.get(method, method.replace('_', ' ').title() or 'Cash')
