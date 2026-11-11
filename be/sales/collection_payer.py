"""
Payer identity and M-Pesa destination (till vs bank) for debt collections.

Used when recording wallet settlements so operators can name who paid, their
phone, and whether an M-Pesa code came via till or bank — then filter reports
by those fields.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError

MPESA_DESTINATION_TILL = 'till'
MPESA_DESTINATION_BANK = 'bank'
MPESA_DESTINATION_CHOICES = (
    (MPESA_DESTINATION_TILL, 'Till'),
    (MPESA_DESTINATION_BANK, 'Bank'),
)
MPESA_DESTINATION_VALUES = frozenset({MPESA_DESTINATION_TILL, MPESA_DESTINATION_BANK})

PAYER_NAME_MAX_LEN = 120
PAYER_PHONE_MAX_LEN = 32

_PHONE_DIGITS = re.compile(r'\D+')


def mpesa_destination_label(value: str) -> str:
    """
    Human label for a stored M-Pesa destination.

    Args:
        value: ``till``, ``bank``, or blank.

    Returns:
        Display label, or empty string when blank/unknown.
    """
    key = (value or '').strip().lower()
    for choice, label in MPESA_DESTINATION_CHOICES:
        if choice == key:
            return label
    return ''


def normalize_payer_name(raw: Optional[str]) -> str:
    """
    Strip and cap payer name length.

    Args:
        raw: Free-text name or None.

    Returns:
        Trimmed name of at most ``PAYER_NAME_MAX_LEN`` characters (may be empty).
    """
    return (raw or '').strip()[:PAYER_NAME_MAX_LEN]


def normalize_payer_phone(raw: Optional[str]) -> str:
    """
    Keep digits and a leading ``+`` for payer phone.

    Args:
        raw: Phone string or None.

    Returns:
        Normalized phone of at most ``PAYER_PHONE_MAX_LEN`` characters.
    """
    text = (raw or '').strip()
    if not text:
        return ''
    if text.startswith('+'):
        digits = _PHONE_DIGITS.sub('', text[1:])
        return ('+' + digits)[:PAYER_PHONE_MAX_LEN]
    return _PHONE_DIGITS.sub('', text)[:PAYER_PHONE_MAX_LEN]


def normalize_mpesa_destination(raw: Optional[str], *, payment_method: str) -> str:
    """
    Normalize destination; clear it for non-M-Pesa methods.

    Args:
        raw: ``till``, ``bank``, or blank.
        payment_method: Settlement method (``cash`` / ``mpesa``).

    Returns:
        ``till``, ``bank``, or ``''``.

    Raises:
        ValidationError: When M-Pesa and value is not till/bank.
    """
    method = (payment_method or '').strip().lower()
    dest = (raw or '').strip().lower()
    if method != 'mpesa':
        return ''
    if not dest:
        return ''
    if dest not in MPESA_DESTINATION_VALUES:
        raise ValidationError(
            {'mpesa_destination': 'Choose whether the M-Pesa code came via till or bank.'}
        )
    return dest


def validate_collection_payer_fields(
    *,
    payment_method: str,
    reference: str = '',
    payer_name: str = '',
    payer_phone: str = '',
    mpesa_destination: str = '',
    require_payer: bool = True,
    require_mpesa_destination_for_code: bool = True,
) -> Dict[str, str]:
    """
    Validate and normalize payer / destination fields for a debt collection.

    Args:
        payment_method: ``cash`` or ``mpesa``.
        reference: M-Pesa receipt or other reference (may be blank for cash).
        payer_name: Who paid (not necessarily the customer on file).
        payer_phone: Payer phone number.
        mpesa_destination: ``till`` or ``bank`` when an M-Pesa code is entered.
        require_payer: When True and method is not cash, name and phone are
            required (feature on). Cash collections never require who-paid.
        require_mpesa_destination_for_code: When True and method is mpesa with
            a non-empty reference, destination must be till or bank.

    Returns:
        Dict with normalized ``payer_name``, ``payer_phone``, ``mpesa_destination``.
        Cash clears unused payer fields when they were not provided.

    Raises:
        ValidationError: Dict of field errors when required values are missing
            or destination is invalid.
    """
    errors: Dict[str, Any] = {}
    name = normalize_payer_name(payer_name)
    phone = normalize_payer_phone(payer_phone)
    method = (payment_method or '').strip().lower()
    ref = (reference or '').strip()
    # Cash is face-to-face — do not force "who paid" / phone.
    effective_require_payer = bool(require_payer) and method != 'cash'

    if effective_require_payer:
        if not name:
            errors['payer_name'] = 'Enter the name of who paid.'
        if not phone:
            errors['payer_phone'] = 'Enter the phone number of who paid.'
        elif len(_PHONE_DIGITS.sub('', phone.lstrip('+'))) < 9:
            errors['payer_phone'] = 'Enter a valid phone number (at least 9 digits).'
    elif phone and len(_PHONE_DIGITS.sub('', phone.lstrip('+'))) < 9:
        # Optional phone on cash: if typed, still validate shape.
        errors['payer_phone'] = 'Enter a valid phone number (at least 9 digits).'

    try:
        dest = normalize_mpesa_destination(mpesa_destination, payment_method=method)
    except ValidationError as exc:
        message_dict = getattr(exc, 'message_dict', None)
        if message_dict:
            errors.update(message_dict)
        else:
            errors['mpesa_destination'] = str(exc)
        dest = ''

    if (
        require_mpesa_destination_for_code
        and method == 'mpesa'
        and ref
        and not dest
    ):
        errors['mpesa_destination'] = (
            'Say whether this M-Pesa code came via till or bank before saving.'
        )

    if errors:
        raise ValidationError(errors)

    return {
        'payer_name': name,
        'payer_phone': phone,
        'mpesa_destination': dest,
    }
