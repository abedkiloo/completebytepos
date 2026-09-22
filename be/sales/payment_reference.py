"""Validation for payment amounts and non-cash payment references."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError

from utils.field_types import AMOUNT_EXAMPLE

MPESA_RECEIPT_EXAMPLE = 'QHX7K2L9M1'
MPESA_RECEIPT_LENGTH = 10

_MPESA_CODE_RE = re.compile(r'^[A-Z0-9]+$')
_WHITESPACE_RE = re.compile(r'\s+')


def normalize_payment_reference(value: str | None) -> str:
    return str(value or '').strip()


def payment_reference_required(payment_method: str) -> bool:
    return payment_method not in ('cash', 'wallet')


def normalize_mpesa_receipt(value: str | None) -> str:
    return _WHITESPACE_RE.sub('', str(value or '').strip()).upper()


def mpesa_receipt_error(value: str | None) -> str | None:
    """Return an informative field message, or None when the code is valid."""
    code = normalize_mpesa_receipt(value)
    if not code:
        return (
            f'Enter the 10-character M-Pesa code from the SMS, e.g. {MPESA_RECEIPT_EXAMPLE}'
        )
    if not _MPESA_CODE_RE.fullmatch(code):
        return f'Use letters and numbers only, e.g. {MPESA_RECEIPT_EXAMPLE}'
    if len(code) != MPESA_RECEIPT_LENGTH:
        return (
            f'Expected 10 characters (you entered {len(code)}), e.g. {MPESA_RECEIPT_EXAMPLE}'
        )
    return None


def validate_sale_payment_reference(payment_method: str, reference: str | None) -> str:
    """Return stripped reference; raise ValidationError when required but missing."""
    ref = normalize_payment_reference(reference)
    if payment_reference_required(payment_method) and not ref:
        raise ValidationError(
            'Enter the payment reference (e.g. M-Pesa confirmation code or card details).'
        )
    return ref
