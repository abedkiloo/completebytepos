"""Customer lookup for POS, the directory, and the field.

A search matches the duka name, owner, contact, code, email, tax id, phone,
or the place already stored on the customer (county, sub-county, ward, city,
or address). Phone digits match both 07… and 2547… forms.
"""

from __future__ import annotations

import re

from django.db.models import F, Q, Value
from django.db.models.functions import Replace


def _digits_only(value: str) -> str:
    return re.sub(r'\D+', '', value or '')


def _phone_search_variants(digits: str) -> list[str]:
    """Kenya-style variants so 07… and 2547… match the same phone."""
    variants = [digits]
    if digits.startswith('0') and len(digits) >= 9:
        variants.append(f'254{digits[1:]}')
    if digits.startswith('254') and len(digits) >= 12:
        variants.append(f'0{digits[3:]}')
    if digits.startswith('2540') and len(digits) >= 13:
        variants.append(digits[3:])
    return sorted({v for v in variants if v}, key=len, reverse=True)


def _phone_digits_expression():
    expression = F('phone')
    for ch in ('+', ' ', '-', '(', ')', '.', '/'):
        expression = Replace(expression, Value(ch), Value(''))
    return expression


def apply_customer_search(queryset, search: str | None):
    """
    Keep customers whose name or place matches the typed text.

    Args:
        queryset: Customer rows already limited by who may see them.
        search: Free text, 0–100 characters after trimming. Blank returns
            the queryset unchanged.

    Returns:
        QuerySet: Same rows, filtered. A phone of at least 3 digits also
        matches the 07 and 254 forms. No writes.

    Raises:
        None.
    """
    term = (search or '').strip()[:100]
    if not term:
        return queryset

    query = (
        Q(name__icontains=term)
        | Q(owner_name__icontains=term)
        | Q(contact_person__icontains=term)
        | Q(customer_code__icontains=term)
        | Q(email__icontains=term)
        | Q(phone__icontains=term)
        | Q(tax_id__icontains=term)
        | Q(county__icontains=term)
        | Q(sub_county__icontains=term)
        | Q(ward__icontains=term)
        | Q(city__icontains=term)
        | Q(address__icontains=term)
    )

    digits = _digits_only(term)
    if len(digits) >= 3:
        annotated = queryset.annotate(_phone_digits=_phone_digits_expression())
        phone_q = Q()
        for variant in _phone_search_variants(digits):
            phone_q |= Q(_phone_digits__icontains=variant)
        return annotated.filter(query | phone_q)

    return queryset.filter(query)
