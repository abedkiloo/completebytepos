"""Informative typed-input validation shared by serializers.

Messages tell the caller the expected type, an example, and what was wrong.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

AMOUNT_EXAMPLE = '250.00'
EMAIL_EXAMPLE = 'name@example.com'
PHONE_EXAMPLE = '0712 345 678'
DATE_EXAMPLE = '2026-09-22'
QUANTITY_EXAMPLE = '3'
NAME_EXAMPLE = 'Jane Wambua'

_EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
_MONEY_RE = re.compile(r'^-?\d+(\.\d{1,2})?$')
_INT_RE = re.compile(r'^-?\d+$')
_ISO_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def money_error_messages(*, allow_zero: bool = False) -> dict[str, str]:
    min_msg = (
        f'Amount cannot be negative, e.g. {AMOUNT_EXAMPLE}'
        if allow_zero
        else f'Amount must be greater than zero, e.g. {AMOUNT_EXAMPLE}'
    )
    invalid = f'Use numbers only, up to 2 decimal places, e.g. {AMOUNT_EXAMPLE}'
    return {
        'required': f'Enter a KES amount, e.g. {AMOUNT_EXAMPLE}',
        'null': f'Enter a KES amount, e.g. {AMOUNT_EXAMPLE}',
        'invalid': invalid,
        'max_digits': invalid,
        'max_decimal_places': invalid,
        'min_value': min_msg,
    }


def date_error_messages(*, label: str = 'date') -> dict[str, str]:
    invalid = f'Use YYYY-MM-DD, e.g. {DATE_EXAMPLE}'
    return {
        'required': f'Enter a {label}, e.g. {DATE_EXAMPLE}',
        'null': f'Enter a {label}, e.g. {DATE_EXAMPLE}',
        'invalid': invalid,
        'datetime': invalid,
    }


def integer_error_messages(*, label: str = 'whole number') -> dict[str, str]:
    invalid = f'Use a whole number (no decimals), e.g. {QUANTITY_EXAMPLE}'
    return {
        'required': f'Enter a {label}, e.g. {QUANTITY_EXAMPLE}',
        'invalid': invalid,
        'min_value': f'Must be zero or more, e.g. {QUANTITY_EXAMPLE}',
    }


def email_error_messages() -> dict[str, str]:
    return {
        'required': f'Enter an email, e.g. {EMAIL_EXAMPLE}',
        'invalid': f'Enter an email like {EMAIL_EXAMPLE}',
        'blank': f'Enter an email, e.g. {EMAIL_EXAMPLE}',
    }


def required_text_error(
    value,
    *,
    label: str,
    example: str,
    min_length: int = 1,
) -> str | None:
    if value is None:
        text = ''
    else:
        text = str(value).strip()
    if not text:
        return f'Enter {label}, e.g. {example}'
    if len(text) < min_length:
        titled = label[:1].upper() + label[1:]
        return f'{titled} must be at least {min_length} characters, e.g. {example}'
    return None


def email_error(value, *, required: bool = False) -> str | None:
    text = '' if value is None else str(value).strip()
    if not text:
        if required:
            return f'Enter an email, e.g. {EMAIL_EXAMPLE}'
        return None
    if not _EMAIL_RE.fullmatch(text):
        shown = text if len(text) <= 40 else f'{text[:37]}...'
        return f'Enter an email like {EMAIL_EXAMPLE}. "{shown}" is not a valid email.'
    return None


def date_error(value, *, required: bool = True, label: str = 'date') -> str | None:
    if value in (None, ''):
        if required:
            return f'Enter a {label}, e.g. {DATE_EXAMPLE}'
        return None
    if isinstance(value, datetime):
        return None
    if isinstance(value, date):
        return None
    text = str(value).strip()
    if 'T' in text:
        text = text[:10]
    if not _ISO_DATE_RE.fullmatch(text):
        return f'Use YYYY-MM-DD, e.g. {DATE_EXAMPLE}'
    try:
        datetime.strptime(text, '%Y-%m-%d')
    except ValueError:
        return f'Use a real calendar date, e.g. {DATE_EXAMPLE}'
    return None


def money_error(
    value,
    *,
    required: bool = True,
    allow_zero: bool = False,
    allow_negative: bool = False,
) -> str | None:
    if value in (None, ''):
        if required:
            return f'Enter a KES amount, e.g. {AMOUNT_EXAMPLE}'
        return None
    if isinstance(value, (int, float, Decimal)):
        amount = Decimal(str(value))
    else:
        text = str(value).strip().replace(',', '')
        if not _MONEY_RE.fullmatch(text):
            return f'Use numbers only, up to 2 decimal places, e.g. {AMOUNT_EXAMPLE}'
        amount = Decimal(text)
    if not allow_negative and amount < 0:
        return f'Amount cannot be negative, e.g. {AMOUNT_EXAMPLE}'
    if not allow_zero and amount <= 0:
        return f'Amount must be greater than zero, e.g. {AMOUNT_EXAMPLE}'
    return None


def integer_error(
    value,
    *,
    required: bool = False,
    min_value: int = 0,
    label: str = 'whole number',
    example: str = QUANTITY_EXAMPLE,
) -> str | None:
    if value in (None, ''):
        if required:
            return f'Enter a {label}, e.g. {example}'
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        text = str(value).strip()
        if not _INT_RE.fullmatch(text):
            return f'Use a whole number (no decimals), e.g. {example}'
        number = int(text)
    else:
        number = value
    if number < min_value:
        titled = label[:1].upper() + label[1:]
        return f'{titled} must be at least {min_value}, e.g. {example}'
    return None


def raise_field_error(message: str | None) -> None:
    """Raise a DRF ValidationError when ``message`` is set."""
    if not message:
        return
    from rest_framework import serializers

    raise serializers.ValidationError(message)
