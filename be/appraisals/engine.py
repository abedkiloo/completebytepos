"""Pure 5-star appraisal math. All figures come from the admin template."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .policy import _decimal, _float


def money(value) -> Decimal:
    return _decimal(value, 0)


def pick_band(amount, bands: list[dict[str, Any]]) -> dict[str, Any]:
    amount = money(amount)
    chosen = None
    for band in sorted(bands or [], key=lambda b: money(b.get('min')), reverse=True):
        if amount >= money(band.get('min')):
            chosen = band
            break
    if chosen is None:
        fallback = sorted(bands or [], key=lambda b: money(b.get('min')))
        return fallback[0] if fallback else {'min': 0, 'stars': 1, 'bonus': 0, 'label': ''}
    return chosen


def next_band(amount, bands: list[dict[str, Any]]) -> dict[str, Any] | None:
    current = pick_band(amount, bands)
    higher = [b for b in (bands or []) if money(b.get('min')) > money(current.get('min'))]
    if not higher:
        return None
    return min(higher, key=lambda b: money(b.get('min')))


def band_progress(amount, bands: list[dict[str, Any]]) -> float:
    current = pick_band(amount, bands)
    nxt = next_band(amount, bands)
    if nxt is None:
        return 1.0
    span = money(nxt.get('min')) - money(current.get('min'))
    if span <= 0:
        return 1.0
    ratio = (money(amount) - money(current.get('min'))) / span
    return float(max(Decimal('0'), min(Decimal('1'), ratio)))


def daily_star(amount, template: dict[str, Any]) -> dict[str, Any]:
    bands = template.get('daily_star_bands') or []
    band = pick_band(amount, bands)
    nxt = next_band(amount, bands)
    sales = money(amount)
    target = money(template.get('daily_target') or 0)
    amount_to_next = money(nxt['min']) - sales if nxt else Decimal('0')
    amount_to_target = max(Decimal('0'), target - sales)
    stars = _float(band.get('stars'), 1)
    return {
        'sales': float(sales),
        'stars': stars,
        'label': str(band.get('label') or ''),
        'next_stars': _float(nxt.get('stars'), stars) if nxt else stars,
        'next_min': float(money(nxt['min'])) if nxt else None,
        'amount_to_next': float(max(Decimal('0'), amount_to_next)),
        'target': float(target),
        'amount_to_target': float(amount_to_target),
        'progress': band_progress(amount, bands),
        'target_progress': float(min(Decimal('1'), sales / target)) if target > 0 else 1.0,
        'tone': star_tone(stars),
    }


def monthly_bonus(amount, template: dict[str, Any]) -> dict[str, Any]:
    bands = template.get('monthly_bonus_bands') or []
    band = pick_band(amount, bands)
    nxt = next_band(amount, bands)
    sales = money(amount)
    stars = _float(band.get('stars'), 1)
    bonus = money(band.get('bonus'))
    amount_to_next = money(nxt['min']) - sales if nxt else Decimal('0')
    return {
        'sales': float(sales),
        'stars': stars,
        'bonus': float(bonus),
        'label': str(band.get('label') or ''),
        'next_stars': _float(nxt.get('stars'), stars) if nxt else stars,
        'next_bonus': float(money(nxt.get('bonus'))) if nxt else float(bonus),
        'next_min': float(money(nxt['min'])) if nxt else None,
        'amount_to_next': float(max(Decimal('0'), amount_to_next)),
        'progress': band_progress(amount, bands),
        'tone': star_tone(stars),
    }


def monthly_average(star_total, working_days) -> float:
    days = max(1, int(working_days or 1))
    return float(money(star_total) / Decimal(days))


def is_four_star_month(average, template: dict[str, Any]) -> bool:
    return float(average or 0) >= float(template.get('four_star_month_min_avg') or 4)


def year_end_result(monthly_averages: list[float], template: dict[str, Any]) -> dict[str, Any]:
    avgs = list(monthly_averages) + [0.0] * (12 - len(monthly_averages))
    avgs = avgs[:12]
    annual_avg = sum(avgs) / 12.0
    threshold = float(template.get('four_star_month_min_avg') or 4)
    annual_needed = float(template.get('annual_avg_required') or 4)
    months_needed = int(template.get('four_star_months_required') or 8)
    four_star_months = sum(1 for avg in avgs if avg >= threshold)
    qualifies = annual_avg >= annual_needed and four_star_months >= months_needed
    increment = float(template.get('year_end_increment') or 0) if qualifies else 0.0
    basic = float(template.get('basic_pay') or 0)
    return {
        'annual_average': round(annual_avg, 4),
        'four_star_months': four_star_months,
        'four_star_months_required': months_needed,
        'qualifies': qualifies,
        'increment_awarded': increment,
        'basic_pay': basic,
        'new_basic': basic + increment,
        'summary': year_end_summary(annual_avg, four_star_months, months_needed, qualifies),
    }


def year_end_summary(annual_avg, four_star_months, months_needed, qualifies) -> str:
    if qualifies:
        return 'Gets the permanent increment. New basic applies at year-end.'
    if annual_avg >= 4.0 and four_star_months < months_needed:
        return 'No increment. Needs consistency — more 4-Star months.'
    return 'No increment. Stays at current basic.'


def star_tone(stars) -> str:
    value = float(stars or 0)
    if value >= 5:
        return 'gold'
    if value >= 4.5:
        return 'teal'
    if value >= 4:
        return 'emerald'
    if value >= 3:
        return 'amber'
    if value >= 2:
        return 'orange'
    return 'rose'


def greeting_copy(
    today: dict[str, Any],
    month: dict[str, Any],
    year: dict[str, Any],
    *,
    show_increment: bool = False,
) -> dict[str, Any]:
    stars = float(today.get('stars') or 1)
    to_target = float(today.get('amount_to_target') or 0)
    if stars >= 5:
        headline = 'Over target — 5 Stars today'
        detail = (
            'Keep talking with customers the same way: follow up, listen, '
            'and make it easy for them to call you first tomorrow.'
        )
    elif stars >= 4:
        headline = 'Target met — 4 Stars today'
        detail = (
            'Use today’s five moves to lock in tomorrow: follow-ups, '
            'clear conversations, and one new customer.'
        )
    else:
        headline = f'{_star_word(stars)} day — KES {int(to_target):,} to hit the daily target'
        detail = (
            'Close the gap by following up, talking well, and finding one more customer. '
            'Five moves for today are below.'
        )

    month_avg = float(month.get('official_average') or 0)
    detail = f'{detail} Monthly average {month_avg:.2f}/5 toward a 4-star month.'
    if show_increment:
        four_count = int(year.get('four_star_months') or 0)
        needed = int(year.get('four_star_months_required') or 8)
        detail = f'{detail} {four_count}/{needed} four-star months this year.'
    return {
        'headline': headline,
        'detail': detail,
        'tone': today.get('tone') or star_tone(stars),
    }


def _star_word(stars) -> str:
    value = int(float(stars or 1))
    return f'{value}-Star'
