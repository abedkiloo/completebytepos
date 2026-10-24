"""Attendance adapter stub — returns zero until an attendance module exists."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def fetch_absence_deduction(
    employee,
    *,
    year: int,
    month: int,
    basic_salary: Decimal | None = None,
) -> dict[str, Any]:
    """
    Interface for future unpaid-leave / absence deductions.

    Always returns amount 0 with ``available=False`` until wired.
    """
    return {
        'amount': Decimal('0.00'),
        'meta': {
            'source': 'attendance',
            'available': False,
            'stub': True,
            'period': f'{year}-{month:02d}',
            'employee_id': getattr(employee, 'employee_id', None),
            'basic_salary': str(basic_salary or 0),
            'message': 'Attendance module not installed — deduction skipped',
        },
    }
