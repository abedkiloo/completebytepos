"""Configurable 5-star appraisal template (admin-owned, JSON in ModuleSetting)."""

from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
from typing import Any

from settings.settings_service import SettingsService

MODULE = 'appraisals'
TEMPLATE_KEY = 'template'

CONTRACT_LINE = (
    'An employee who maintains a 4-Star rating (Average 4.0/5) for at least '
    '8 months out of 12 months in a calendar year shall qualify for a '
    'permanent salary increment of KES 3,000 at year-end.'
)

BONUS_POLICY_LINE = (
    'Monthly bonus is based on closed sales collected. 600K = 2 Stars = 2K bonus. '
    '1M = 4 Stars = 7K bonus. 1.5M = 5 Stars = 10K maximum bonus.'
)

DEFAULT_DAILY_BANDS = [
    {'min': 0, 'stars': 1, 'label': ''},
    {'min': 10000, 'stars': 2, 'label': ''},
    {'min': 16000, 'stars': 3, 'label': ''},
    {'min': 20000, 'stars': 4, 'label': 'TARGET MET'},
    {'min': 24000, 'stars': 5, 'label': 'OVER TARGET'},
]

DEFAULT_BONUS_BANDS = [
    {'min': 0, 'stars': 1, 'bonus': 0, 'label': ''},
    {'min': 600000, 'stars': 2, 'bonus': 2000, 'label': ''},
    {'min': 800000, 'stars': 3, 'bonus': 4000, 'label': ''},
    {'min': 1000000, 'stars': 4, 'bonus': 7000, 'label': ''},
    {'min': 1200000, 'stars': 4.5, 'bonus': 8500, 'label': ''},
    {'min': 1500000, 'stars': 5, 'bonus': 10000, 'label': 'MAX'},
]

DEFAULT_TEMPLATE: dict[str, Any] = {
    'basic_pay': 15000,
    'daily_target': 20000,
    'year_end_increment': 3000,
    'working_days': 26,
    'four_star_month_min_avg': 4.0,
    'four_star_months_required': 8,
    'annual_avg_required': 4.0,
    'daily_star_bands': DEFAULT_DAILY_BANDS,
    'monthly_bonus_bands': DEFAULT_BONUS_BANDS,
    'contract_line': CONTRACT_LINE,
    'bonus_policy_line': BONUS_POLICY_LINE,
}


def _decimal(value, default=0) -> Decimal:
    if value is None or value == '':
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _float(value, default=0.0) -> float:
    return float(_decimal(value, default))


def _int(value, default=0) -> int:
    try:
        return int(_decimal(value, default))
    except (TypeError, ValueError, InvalidOperation):
        return int(default)


def _normalize_daily_band(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    return {
        'min': _float(raw.get('min'), 0),
        'stars': _float(raw.get('stars'), 1),
        'label': str(raw.get('label') or ''),
    }


def _normalize_bonus_band(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    return {
        'min': _float(raw.get('min'), 0),
        'stars': _float(raw.get('stars'), 1),
        'bonus': _float(raw.get('bonus'), 0),
        'label': str(raw.get('label') or ''),
    }


def _sorted_bands(bands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(bands, key=lambda b: _float(b.get('min'), 0))


class PolicyError(ValueError):
    pass


def default_template() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_TEMPLATE)


def normalize_template(raw: Any) -> dict[str, Any]:
    data = default_template()
    if not isinstance(raw, dict):
        return data

    if 'basic_pay' in raw:
        data['basic_pay'] = max(0, _float(raw['basic_pay'], data['basic_pay']))
    if 'daily_target' in raw:
        data['daily_target'] = max(0, _float(raw['daily_target'], data['daily_target']))
    if 'year_end_increment' in raw:
        data['year_end_increment'] = max(0, _float(raw['year_end_increment'], data['year_end_increment']))
    if 'working_days' in raw:
        days = _int(raw['working_days'], data['working_days'])
        data['working_days'] = min(31, max(1, days))
    if 'four_star_month_min_avg' in raw:
        data['four_star_month_min_avg'] = max(0, _float(raw['four_star_month_min_avg'], 4))
    if 'four_star_months_required' in raw:
        needed = _int(raw['four_star_months_required'], 8)
        data['four_star_months_required'] = min(12, max(1, needed))
    if 'annual_avg_required' in raw:
        data['annual_avg_required'] = max(0, _float(raw['annual_avg_required'], 4))
    if 'contract_line' in raw:
        data['contract_line'] = str(raw.get('contract_line') or data['contract_line'])
    if 'bonus_policy_line' in raw:
        data['bonus_policy_line'] = str(raw.get('bonus_policy_line') or data['bonus_policy_line'])

    daily = raw.get('daily_star_bands')
    if isinstance(daily, list) and daily:
        bands = [b for b in (_normalize_daily_band(row) for row in daily) if b]
        if bands:
            data['daily_star_bands'] = _sorted_bands(bands)

    bonus = raw.get('monthly_bonus_bands')
    if isinstance(bonus, list) and bonus:
        bands = [b for b in (_normalize_bonus_band(row) for row in bonus) if b]
        if bands:
            data['monthly_bonus_bands'] = _sorted_bands(bands)

    return data


def validate_template(template: dict[str, Any]) -> dict[str, Any]:
    data = normalize_template(template)
    if not data['daily_star_bands']:
        raise PolicyError('Daily star bands cannot be empty.')
    if not data['monthly_bonus_bands']:
        raise PolicyError('Monthly bonus bands cannot be empty.')
    mins = [b['min'] for b in data['daily_star_bands']]
    if len(mins) != len(set(mins)):
        raise PolicyError('Daily star band minimums must be unique.')
    bonus_mins = [b['min'] for b in data['monthly_bonus_bands']]
    if len(bonus_mins) != len(set(bonus_mins)):
        raise PolicyError('Monthly bonus band minimums must be unique.')
    return data


def greet_when_no_sticky_notes() -> bool:
    return bool(SettingsService.get(MODULE, 'greet_when_no_sticky_notes', default=True))


def show_on_home() -> bool:
    return bool(SettingsService.get(MODULE, 'show_on_home', default=True))


def load_template() -> dict[str, Any]:
    stored = SettingsService.get(MODULE, TEMPLATE_KEY, default=None)
    return normalize_template(stored)


def save_template(raw: dict[str, Any], *, user=None) -> dict[str, Any]:
    data = validate_template(raw)
    SettingsService.set(MODULE, TEMPLATE_KEY, data, user=user)
    flags = {}
    if 'greet_when_no_sticky_notes' in raw:
        flags['greet_when_no_sticky_notes'] = bool(raw['greet_when_no_sticky_notes'])
    if 'show_on_home' in raw:
        flags['show_on_home'] = bool(raw['show_on_home'])
    if flags:
        SettingsService.set_many(MODULE, flags, user=user)
    return public_policy(data)


def public_policy(template: dict[str, Any] | None = None) -> dict[str, Any]:
    data = copy.deepcopy(template or load_template())
    data['greet_when_no_sticky_notes'] = greet_when_no_sticky_notes()
    data['show_on_home'] = show_on_home()
    return data
