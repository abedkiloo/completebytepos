"""Loans adapter stub — returns zero until an HR loans module exists."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def fetch_loan_deduction(
    employee,
    *,
    year: int,
    month: int,
) -> dict[str, Any]:
    """
    Interface for future loan repayment deductions.

    Always returns amount 0 with ``available=False`` until wired.
    """
    return {
        'amount': Decimal('0.00'),
        'meta': {
            'source': 'loans',
            'available': False,
            'stub': True,
            'period': f'{year}-{month:02d}',
            'employee_id': getattr(employee, 'employee_id', None),
            'message': 'HR loans module not installed — deduction skipped',
        },
    }
