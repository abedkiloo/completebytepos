"""Validation for non-cash sale payment references."""

from __future__ import annotations

from django.core.exceptions import ValidationError


def normalize_payment_reference(value: str | None) -> str:
    return str(value or '').strip()


def payment_reference_required(payment_method: str) -> bool:
    return payment_method not in ('cash', 'wallet')


def validate_sale_payment_reference(payment_method: str, reference: str | None) -> str:
    """Return stripped reference; raise ValidationError when required but missing."""
    ref = normalize_payment_reference(reference)
    if payment_reference_required(payment_method) and not ref:
        raise ValidationError(
            'Enter the payment reference (e.g. M-Pesa confirmation code or card details).'
        )
    return ref
