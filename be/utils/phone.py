"""Normalize phone numbers with a default country prefix (Kenya 254)."""

from __future__ import annotations


class PhoneNumberError(ValueError):
    """Invalid or incomplete phone number."""


def default_country_code() -> str:
    try:
        from django.conf import settings

        raw = getattr(settings, 'DEFAULT_PHONE_COUNTRY_CODE', '254')
    except Exception:
        raw = '254'
    digits = ''.join(c for c in str(raw or '254') if c.isdigit())
    return digits or '254'


def normalize_phone_number(
    value,
    *,
    required: bool = False,
    default_country: str | None = None,
) -> str:
    """
    Store digits with a country prefix.

    Default country is 254. Accepts 07…, 7…, +254…, and 254….
    Blank is allowed unless ``required`` is True.
    """
    raw = '' if value is None else str(value).strip()
    if not raw:
        if required:
            raise PhoneNumberError('Phone number is required.')
        return ''

    digits = ''.join(c for c in raw if c.isdigit())
    if not digits:
        raise PhoneNumberError('Enter a valid phone number.')

    country = default_country or default_country_code()

    if digits.startswith(country):
        national = digits[len(country):]
        if national.startswith('0'):
            national = national[1:]
        digits = country + national
    elif digits.startswith('0') and len(digits) >= 9:
        digits = country + digits[1:]
    elif len(digits) == 9 and digits[0] in '17':
        digits = country + digits
    elif 10 <= len(digits) <= 15 and not digits.startswith('0'):
        return digits
    else:
        raise PhoneNumberError(
            f'Enter a valid phone number with country code (default {country}).'
        )

    if country == '254' and len(digits) != 12:
        raise PhoneNumberError(
            'Enter a valid Kenyan number (07…, 7…, or 254…).'
        )
    if len(digits) < 10 or len(digits) > 15:
        raise PhoneNumberError(
            f'Enter a valid phone number with country code (default {country}).'
        )
    return digits


def validate_optional_phone(value) -> str:
    """Normalize for DRF ``validate_<field>`` methods. Blank stays blank."""
    from rest_framework import serializers

    try:
        return normalize_phone_number(value)
    except PhoneNumberError as exc:
        raise serializers.ValidationError(str(exc)) from exc
