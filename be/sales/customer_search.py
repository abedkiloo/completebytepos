"""Customer lookup for POS and past-sale entry — duka, owner, contact, code, email, or phone."""

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
    """Filter by duka name, owner, contact person, code, email, tax id, or phone."""
    term = (search or '').strip()
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
    )

    digits = _digits_only(term)
    if len(digits) >= 3:
        annotated = queryset.annotate(_phone_digits=_phone_digits_expression())
        phone_q = Q()
        for variant in _phone_search_variants(digits):
            phone_q |= Q(_phone_digits__icontains=variant)
        return annotated.filter(query | phone_q)

    return queryset.filter(query)
