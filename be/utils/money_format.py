"""Display helpers for money and counts (thousand separators)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def format_grouped_number(amount: Any, *, decimals: int | None = 2) -> str:
    """
    Format a number with comma grouping, e.g. 1000 -> 1,000 or 1,000.00.

    When ``decimals`` is None, integers stay without a fraction; floats keep
    up to 2 places without trailing zeros.
    """
    try:
        value = Decimal(str(amount if amount is not None else 0))
    except (InvalidOperation, ValueError, TypeError):
        value = Decimal('0')

    if decimals is None:
        if value == value.to_integral_value():
            return f'{int(value):,}'
        quantized = value.quantize(Decimal('0.01'))
        text = f'{quantized:,f}'
        if text.endswith('.00'):
            return text[:-3]
        return text.rstrip('0').rstrip('.') if '.' in text else text

    if decimals <= 0:
        return f'{int(value.to_integral_value()):,}'

    quantum = Decimal('1').scaleb(-decimals)
    quantized = value.quantize(quantum)
    return f'{quantized:,.{decimals}f}'


def format_kes(amount: Any, *, decimals: int | None = 2) -> str:
    return f'KES {format_grouped_number(amount, decimals=decimals)}'
