"""
Mid-join salary proration for monthly payroll.

A pay month is treated as at least four weeks (28 days). Employees who join
part-way through the period receive a proportional share of basic salary
(e.g. join at the midpoint → about half).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from payroll.engine import money

ZERO = Decimal('0.00')
ONE = Decimal('1')
DEFAULT_MIN_MONTH_DAYS = 28  # four weeks
MIN_MONTH_DAYS_FLOOR = 28
MIN_MONTH_DAYS_CEILING = 31


def calendar_period_days(period_start: date, period_end: date) -> int:
    """
    Inclusive calendar days in ``[period_start, period_end]``.

    Args:
        period_start: Inclusive start (datetime.date).
        period_end: Inclusive end; must be >= period_start.

    Returns:
        Day count in 1..366. Returns 0 when end is before start.
    """
    if period_end < period_start:
        return 0
    return (period_end - period_start).days + 1


def month_day_denominator(
    period_start: date,
    period_end: date,
    *,
    min_month_days: int = DEFAULT_MIN_MONTH_DAYS,
) -> int:
    """
    Denominator for proration: max(calendar days in period, min_month_days).

    Ensures a month counts as at least four weeks (28 days) even when a
    shorter calendar span is configured.

    Args:
        period_start: Inclusive period start.
        period_end: Inclusive period end.
        min_month_days: Floor days for a full month, typically 28 (4 weeks).
            Clamped to 28–31 when outside that range.

    Returns:
        Positive integer denominator (28–366 typical).
    """
    floor = int(min_month_days or DEFAULT_MIN_MONTH_DAYS)
    if floor < MIN_MONTH_DAYS_FLOOR:
        floor = MIN_MONTH_DAYS_FLOOR
    if floor > MIN_MONTH_DAYS_CEILING:
        floor = MIN_MONTH_DAYS_CEILING
    cal = calendar_period_days(period_start, period_end)
    return max(cal, floor)


def days_worked_in_period(
    *,
    hire_date: date | None,
    period_start: date,
    period_end: date,
) -> int:
    """
    Inclusive days the employee is employed inside the pay period.

    Args:
        hire_date: Employee hire date, or None (treated as employed for full period).
        period_start: Inclusive period start.
        period_end: Inclusive period end.

    Returns:
        0 when hired after period_end; otherwise 1..(period length).
    """
    if hire_date is None:
        return calendar_period_days(period_start, period_end)
    if hire_date > period_end:
        return 0
    start = hire_date if hire_date > period_start else period_start
    return calendar_period_days(start, period_end)


def mid_join_proration_factor(
    *,
    hire_date: date | None,
    period_start: date,
    period_end: date,
    min_month_days: int = DEFAULT_MIN_MONTH_DAYS,
) -> Decimal:
    """
    Fraction of monthly basic due for the period (0..1).

    Join halfway through a 30-day month → ~0.5. Full month → 1.0.
    Denominator is at least ``min_month_days`` (default 28 = 4 weeks).

    Args:
        hire_date: When employment started; None = full period.
        period_start: Run period start.
        period_end: Run period end.
        min_month_days: Month floor in days (28–31).

    Returns:
        Decimal factor quantized to 6 places, capped at 1.
    """
    worked = days_worked_in_period(
        hire_date=hire_date,
        period_start=period_start,
        period_end=period_end,
    )
    if worked <= 0:
        return ZERO
    denom = month_day_denominator(
        period_start, period_end, min_month_days=min_month_days
    )
    if denom <= 0:
        return ZERO
    factor = Decimal(worked) / Decimal(denom)
    if factor > ONE:
        factor = ONE
    return factor.quantize(Decimal('0.000001'))


def apply_basic_proration(
    full_basic,
    *,
    hire_date: date | None,
    period_start: date,
    period_end: date,
    min_month_days: int = DEFAULT_MIN_MONTH_DAYS,
    enabled: bool = True,
) -> tuple[Decimal, dict[str, Any]]:
    """
    Scale monthly basic by mid-join factor when enabled.

    Args:
        full_basic: Unprorated monthly basic (Decimal-compatible).
        hire_date: Employee hire date or None.
        period_start: Pay period start.
        period_end: Pay period end.
        min_month_days: At-least-4-weeks floor (default 28).
        enabled: When False, returns full basic unchanged.

    Returns:
        ``(prorated_basic, meta)`` where meta records factor, days, and flags.
        Amounts use money() (2 dp). Factor meta uses 6 dp string.
    """
    full = money(full_basic)
    meta: dict[str, Any] = {
        'enabled': bool(enabled),
        'full_basic': str(full),
        'min_month_days': int(min_month_days or DEFAULT_MIN_MONTH_DAYS),
        'hire_date': hire_date.isoformat() if hire_date else None,
        'period_start': period_start.isoformat(),
        'period_end': period_end.isoformat(),
    }
    if not enabled:
        meta.update(
            {
                'factor': '1.000000',
                'days_worked': calendar_period_days(period_start, period_end),
                'period_days': month_day_denominator(
                    period_start, period_end, min_month_days=min_month_days
                ),
                'prorated': False,
            }
        )
        return full, meta

    factor = mid_join_proration_factor(
        hire_date=hire_date,
        period_start=period_start,
        period_end=period_end,
        min_month_days=min_month_days,
    )
    worked = days_worked_in_period(
        hire_date=hire_date,
        period_start=period_start,
        period_end=period_end,
    )
    denom = month_day_denominator(
        period_start, period_end, min_month_days=min_month_days
    )
    prorated = money(full * factor)
    meta.update(
        {
            'factor': str(factor),
            'days_worked': worked,
            'period_days': denom,
            'prorated': factor < ONE,
            'prorated_basic': str(prorated),
        }
    )
    return prorated, meta
