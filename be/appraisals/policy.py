"""Configurable 5-star appraisal template (admin-owned, JSON in ModuleSetting)."""

from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
from typing import Any

from settings.settings_service import SettingsService

from .tips import DEFAULT_DAILY_TIP_PACKS, normalize_daily_tip_packs

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
    'manager_daily_target': 35000,
    'role_daily_targets': {
        'Manager': 35000,
        'Sales Personnel': 20000,
        'Field Sales': 20000,
    },
    'year_end_increment': 3000,
    'working_days': 26,
    'four_star_month_min_avg': 4.0,
    'four_star_months_required': 8,
    'annual_avg_required': 4.0,
    'daily_star_bands': DEFAULT_DAILY_BANDS,
    'monthly_bonus_bands': DEFAULT_BONUS_BANDS,
    'contract_line': CONTRACT_LINE,
    'bonus_policy_line': BONUS_POLICY_LINE,
    'daily_tip_packs': DEFAULT_DAILY_TIP_PACKS,
    'show_year_end_increment': False,
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


APPRAISAL_ROLE_SKIP = frozenset({'Super Admin'})
DEFAULT_SALES_ROLES = ('Sales Personnel', 'Field Sales')
DEFAULT_MANAGER_ROLES = ('Manager',)


def _is_manager_role_name(name: str) -> bool:
    n = (name or '').strip()
    if n in DEFAULT_MANAGER_ROLES:
        return True
    return 'manager' in n.lower()


def _normalize_role_daily_targets(
    raw: Any,
    *,
    daily_target: float,
    manager_daily_target: float,
) -> dict[str, float]:
    targets = {
        'Manager': manager_daily_target,
        'Sales Personnel': daily_target,
        'Field Sales': daily_target,
    }
    incoming: Any = None
    if isinstance(raw, dict):
        incoming = raw.get('role_daily_targets')
    if isinstance(incoming, dict):
        rows = incoming.items()
        for name, value in rows:
            key = str(name).strip()
            if not key or key in APPRAISAL_ROLE_SKIP:
                continue
            fallback = manager_daily_target if _is_manager_role_name(key) else daily_target
            targets[key] = max(0, _float(value, fallback))
    elif isinstance(incoming, list):
        for row in incoming:
            if not isinstance(row, dict):
                continue
            key = str(row.get('role') or row.get('name') or '').strip()
            if not key or key in APPRAISAL_ROLE_SKIP:
                continue
            fallback = manager_daily_target if _is_manager_role_name(key) else daily_target
            targets[key] = max(
                0,
                _float(row.get('target', row.get('daily_target')), fallback),
            )
    return dict(sorted(targets.items(), key=lambda item: item[0].lower()))


def catalog_role_names() -> list[str]:
    names = ['Field Sales', 'Manager', 'Sales Personnel']
    try:
        from accounts.models import Role

        extra = (
            Role.objects.filter(
                is_active=True,
                permissions__module__in=['sales', 'pos', 'appraisals'],
            )
            .exclude(name__in=APPRAISAL_ROLE_SKIP)
            .values_list('name', flat=True)
            .distinct()
        )
        for name in extra:
            label = str(name or '').strip()
            if label and label not in names and label not in APPRAISAL_ROLE_SKIP:
                names.append(label)
    except Exception:
        pass
    return sorted(names, key=str.lower)


def merge_role_daily_targets(template: dict[str, Any]) -> dict[str, float]:
    daily = _float(template.get('daily_target'), 20000)
    manager = _float(template.get('manager_daily_target'), 35000)
    targets = dict(template.get('role_daily_targets') or {})
    for name in catalog_role_names():
        targets.setdefault(
            name,
            manager if _is_manager_role_name(name) else daily,
        )
    return dict(sorted(targets.items(), key=lambda item: item[0].lower()))


def resolve_role_daily_target(template: dict[str, Any], role_name: str) -> float:
    targets = template.get('role_daily_targets') or {}
    name = (role_name or '').strip()
    if name and name in targets:
        return _float(targets[name], 0)
    if _is_manager_role_name(name):
        return _float(template.get('manager_daily_target'), 35000)
    return _float(template.get('daily_target'), 20000)


def apply_daily_target(template: dict[str, Any], target: float) -> dict[str, Any]:
    """Copy template with daily_target set and star bands scaled so 4★ is target met."""
    data = copy.deepcopy(template)
    amount = max(0.0, _float(target, 0))
    bands = list(data.get('daily_star_bands') or [])
    four_star = next(
        (band for band in bands if abs(_float(band.get('stars'), 0) - 4) < 0.01),
        None,
    )
    baseline = _float(
        (four_star or {}).get('min') if four_star else data.get('daily_target'),
        0,
    )
    data['daily_target'] = amount
    if amount > 0 and baseline > 0 and bands:
        ratio = amount / baseline
        scaled = []
        for band in bands:
            row = dict(band)
            row['min'] = round(max(0.0, _float(band.get('min'), 0) * ratio), 2)
            scaled.append(row)
        data['daily_star_bands'] = scaled
    return data


def template_for_role(template: dict[str, Any] | None, role_name: str) -> dict[str, Any]:
    data = copy.deepcopy(template or load_template())
    return apply_daily_target(data, resolve_role_daily_target(data, role_name))


def template_for_track(template: dict[str, Any] | None = None, *, manager: bool) -> dict[str, Any]:
    """Back-compat wrapper: sales vs manager default roles."""
    return template_for_role(
        template,
        'Manager' if manager else 'Sales Personnel',
    )


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
    if 'manager_daily_target' in raw:
        data['manager_daily_target'] = max(
            0, _float(raw['manager_daily_target'], data['manager_daily_target'])
        )
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
    if 'show_year_end_increment' in raw:
        data['show_year_end_increment'] = bool(raw.get('show_year_end_increment'))

    data['daily_tip_packs'] = normalize_daily_tip_packs(raw)

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

    data['role_daily_targets'] = _normalize_role_daily_targets(
        raw,
        daily_target=data['daily_target'],
        manager_daily_target=data['manager_daily_target'],
    )
    data['daily_target'] = _float(
        data['role_daily_targets'].get('Sales Personnel', data['daily_target']),
        data['daily_target'],
    )
    data['manager_daily_target'] = _float(
        data['role_daily_targets'].get('Manager', data['manager_daily_target']),
        data['manager_daily_target'],
    )

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
    data['role_daily_targets'] = merge_role_daily_targets(data)
    data['daily_target'] = _float(
        data['role_daily_targets'].get('Sales Personnel', data.get('daily_target')),
        20000,
    )
    data['manager_daily_target'] = _float(
        data['role_daily_targets'].get('Manager', data.get('manager_daily_target')),
        35000,
    )
    data['greet_when_no_sticky_notes'] = greet_when_no_sticky_notes()
    data['show_on_home'] = show_on_home()
    return data
