"""Appraisal / target-delivery bonus adapter for payroll."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import User


def money(value) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal('0.01'))
    except Exception:
        return Decimal('0.00')


def resolve_user_for_employee(employee) -> User | None:
    """Match employee to a login user by email (case-insensitive)."""
    email = (getattr(employee, 'email', None) or '').strip()
    if not email:
        return None
    return User.objects.filter(email__iexact=email, is_active=True).first()


def fetch_appraisal_bonus(
    employee,
    *,
    year: int,
    month: int,
) -> dict[str, Any]:
    """
    Return payable monthly bonus for an employee for the given period.

    Snapshots the appraisals engine result; never mutates appraisal data.
    Returns ``{amount, qualified, meta}``.
    """
    empty = {
        'amount': Decimal('0.00'),
        'qualified': False,
        'meta': {'source': 'appraisals', 'available': False},
    }
    try:
        from appraisals.services import staff_snapshot
    except Exception:
        return {**empty, 'meta': {**empty['meta'], 'error': 'appraisals_unavailable'}}

    user = resolve_user_for_employee(employee)
    if user is None:
        return {
            **empty,
            'meta': {
                'source': 'appraisals',
                'available': True,
                'matched_user': False,
                'reason': 'no_user_email_match',
            },
        }

    try:
        last_day = calendar.monthrange(year, month)[1]
        as_of = date(year, month, last_day)
        progress = staff_snapshot(user, year=year, today=as_of)
        month_block = (progress or {}).get('month') or {}
        amount = money(month_block.get('bonus'))
        qualified = bool(month_block.get('bonus_qualified', amount > 0))
        return {
            'amount': amount,
            'qualified': qualified,
            'meta': {
                'source': 'appraisals',
                'available': True,
                'matched_user': True,
                'user_id': user.id,
                'stars': month_block.get('stars'),
                'bonus_earned': month_block.get('bonus_earned'),
                'bonus_block_reasons': month_block.get('bonus_block_reasons') or [],
                'period': f'{year}-{month:02d}',
            },
        }
    except Exception as exc:
        return {
            **empty,
            'meta': {
                'source': 'appraisals',
                'available': True,
                'matched_user': True,
                'error': str(exc)[:200],
            },
        }
