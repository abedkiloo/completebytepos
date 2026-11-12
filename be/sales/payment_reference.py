"""Validation for payment amounts and non-cash payment references."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError

from utils.field_types import AMOUNT_EXAMPLE

MPESA_RECEIPT_EXAMPLE = 'QHX7K2L9M1'
MPESA_RECEIPT_MIN_LENGTH = 4

_MPESA_CODE_RE = re.compile(r'^[A-Z0-9]+$')
_WHITESPACE_RE = re.compile(r'\s+')


def normalize_payment_reference(value: str | None) -> str:
    return str(value or '').strip()


def payment_reference_required(payment_method: str, *, amount_paid=None) -> bool:
    """M-Pesa code required only when collecting M-Pesa now (not pay later)."""
    if payment_method != 'mpesa':
        return False
    if amount_paid is None:
        return True
    try:
        from decimal import Decimal

        return Decimal(str(amount_paid)) > 0
    except Exception:
        return True


def normalize_mpesa_receipt(value: str | None) -> str:
    return _WHITESPACE_RE.sub('', str(value or '').strip()).upper()


def mpesa_receipt_error(value: str | None) -> str | None:
    """Return an informative field message, or None when the code is valid."""
    code = normalize_mpesa_receipt(value)
    if not code:
        return (
            f'Enter the M-Pesa code from the SMS (at least 4 letters and numbers), '
            f'e.g. {MPESA_RECEIPT_EXAMPLE}'
        )
    if not _MPESA_CODE_RE.fullmatch(code):
        return f'Use letters and numbers only, e.g. {MPESA_RECEIPT_EXAMPLE}'
    if len(code) < MPESA_RECEIPT_MIN_LENGTH:
        return (
            f'Must be at least 4 characters (you entered {len(code)}), '
            f'e.g. {MPESA_RECEIPT_EXAMPLE}'
        )
    return None


def validate_sale_payment_reference(
    payment_method: str,
    reference: str | None,
    *,
    amount_paid=None,
) -> str:
    """Return stripped reference; raise ValidationError when required but missing."""
    ref = normalize_payment_reference(reference)
    if payment_reference_required(payment_method, amount_paid=amount_paid) and not ref:
        raise ValidationError(
            'Enter the M-Pesa confirmation code from the SMS.'
        )
    if payment_method == 'mpesa' and ref:
        err = mpesa_receipt_error(ref)
        if err:
            raise ValidationError(err)
        return normalize_mpesa_receipt(ref)
    return ref


def validate_sale_mpesa_destination(
    payment_method: str,
    destination: str | None,
    *,
    amount_paid=None,
) -> str:
    """
    Require till/bank before an M-Pesa code when collecting now.

    Returns:
        Normalized ``till`` / ``bank`` / ``''``.
    """
    method = (payment_method or '').strip().lower()
    dest = (destination or '').strip().lower()
    collecting = payment_reference_required(method, amount_paid=amount_paid)
    if not collecting:
        return ''
    if dest not in ('till', 'bank'):
        raise ValidationError(
            'Choose whether this M-Pesa payment came via till or bank before entering the code.'
        )
    return dest
