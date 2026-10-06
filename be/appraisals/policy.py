"""Configurable 5-star appraisal template (admin-owned, JSON in ModuleSetting)."""

from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
from typing import Any

from datetime import datetime as _dt, date as _date

from settings.settings_service import SettingsService
from django.utils import timezone

from .tips import DEFAULT_DAILY_TIP_PACKS, normalize_daily_tip_packs

MODULE = 'appraisals'
TEMPLATE_KEY = 'template'

CONTRACT_LINE = (
    'An employee who maintains a 4-Star rating (Average 4.0/5) for at least '
    '8 months out of 12 months in a calendar year shall qualify for a '
    'permanent salary increment of KES 3,000 at year-end.'
)

BONUS_POLICY_LINE = (
    'Monthly bonus starts only at 4 Stars (KES 2,000 base). '
    'Higher sales unlock more for each role, up to KES 10,000 at 5 Stars.'
)

DEFAULT_DAILY_BANDS = [
    {'min': 0, 'stars': 1, 'label': ''},
    {'min': 10000, 'stars': 2, 'label': ''},
    {'min': 16000, 'stars': 3, 'label': ''},
    {'min': 20000, 'stars': 4, 'label': 'TARGET MET'},
    {'min': 24000, 'stars': 5, 'label': 'OVER TARGET'},
]

# Cash bonus begins at 4★ (KES 2,000). Segments below that keep star labels but pay 0.
DEFAULT_BONUS_BANDS = [
    {'min': 0, 'stars': 1, 'bonus': 0, 'label': ''},
    {'min': 600000, 'stars': 2, 'bonus': 0, 'label': ''},
    {'min': 800000, 'stars': 3, 'bonus': 0, 'label': ''},
    {'min': 1000000, 'stars': 4, 'bonus': 2000, 'label': 'BASE'},
    {'min': 1250000, 'stars': 4.5, 'bonus': 6000, 'label': ''},
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
    'bonus_min_stars': 4.0,
    'bonus_cap': 10000,
    'daily_star_bands': DEFAULT_DAILY_BANDS,
    'monthly_bonus_bands': DEFAULT_BONUS_BANDS,
    'contract_line': CONTRACT_LINE,
    'bonus_policy_line': BONUS_POLICY_LINE,
    'daily_tip_packs': DEFAULT_DAILY_TIP_PACKS,
    'show_year_end_increment': False,
    'sales_basis': 'posted_net',
    'status_labels': {
        '5': 'Exceptional',
        '4.5': 'Target exceeded',
        '4': 'Target achieved',
        '3': 'Near target',
        '2': 'Below target',
        '1': 'Needs attention',
    },
    'role_frameworks': {},
    'versions': [],
    'active_from': '',
    'last_change_reason': '',
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


APPRAISAL_ROLE_SKIP = frozenset({'Super Admin', 'Admin', 'Administrator'})
_APPRAISAL_ROLE_SKIP_LOWER = frozenset(name.lower() for name in APPRAISAL_ROLE_SKIP)
DEFAULT_SALES_ROLES = ('Sales Personnel', 'Field Sales')
DEFAULT_MANAGER_ROLES = ('Manager',)


def is_skipped_appraisal_role(name: str) -> bool:
    """Admins are not scored against a personal daily target."""
    return (name or '').strip().lower() in _APPRAISAL_ROLE_SKIP_LOWER


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
            if not key or is_skipped_appraisal_role(key):
                continue
            fallback = manager_daily_target if _is_manager_role_name(key) else daily_target
            targets[key] = max(0, _float(value, fallback))
    elif isinstance(incoming, list):
        for row in incoming:
            if not isinstance(row, dict):
                continue
            key = str(row.get('role') or row.get('name') or '').strip()
            if not key or is_skipped_appraisal_role(key):
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
            if label and label not in names and not is_skipped_appraisal_role(label):
                names.append(label)
    except Exception:
        pass
    return sorted(names, key=str.lower)


def merge_role_daily_targets(template: dict[str, Any]) -> dict[str, float]:
    daily = _float(template.get('daily_target'), 20000)
    manager = _float(template.get('manager_daily_target'), 35000)
    targets = {
        name: value
        for name, value in dict(template.get('role_daily_targets') or {}).items()
        if not is_skipped_appraisal_role(name)
    }
    for name in catalog_role_names():
        targets.setdefault(
            name,
            manager if _is_manager_role_name(name) else daily,
        )
    return dict(sorted(targets.items(), key=lambda item: item[0].lower()))


def resolve_role_daily_target(template: dict[str, Any], role_name: str) -> float:
    targets = template.get('role_daily_targets') or {}
    name = (role_name or '').strip()
    if is_skipped_appraisal_role(name):
        return 0
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


def _normalize_one_framework(raw: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    daily = max(0.0, _float(raw.get('daily_target'), base.get('daily_target') or 20000))
    bands = raw.get('daily_star_bands')
    daily_bands = None
    if isinstance(bands, list) and bands:
        daily_bands = _sorted_bands(
            [b for b in (_normalize_daily_band(row) for row in bands) if b]
        )
    bonus = raw.get('monthly_bonus_bands')
    bonus_bands = None
    if isinstance(bonus, list) and bonus:
        bonus_bands = _sorted_bands(
            [b for b in (_normalize_bonus_band(row) for row in bonus) if b]
        )
    days = _int(raw.get('working_days'), _int(base.get('working_days'), 26))
    months_needed = _int(
        raw.get('four_star_months_required'),
        _int(base.get('four_star_months_required'), 8),
    )
    return {
        'basic_pay': max(0.0, _float(raw.get('basic_pay'), base.get('basic_pay') or 0)),
        'daily_target': daily,
        'year_end_increment': max(
            0.0, _float(raw.get('year_end_increment'), base.get('year_end_increment') or 0)
        ),
        'working_days': min(31, max(1, days)),
        'four_star_month_min_avg': max(
            0.0,
            _float(raw.get('four_star_month_min_avg'), base.get('four_star_month_min_avg') or 4),
        ),
        'four_star_months_required': min(12, max(1, months_needed)),
        'annual_avg_required': max(
            0.0,
            _float(raw.get('annual_avg_required'), base.get('annual_avg_required') or 4),
        ),
        'daily_star_bands': daily_bands,
        'monthly_bonus_bands': bonus_bands,
    }


def _normalize_role_frameworks(raw: Any, base: dict[str, Any]) -> dict[str, Any]:
    incoming = raw.get('role_frameworks') if isinstance(raw, dict) else None
    frameworks: dict[str, Any] = {}
    if isinstance(incoming, dict):
        for name, cfg in incoming.items():
            key = str(name).strip()
            if not key or is_skipped_appraisal_role(key) or not isinstance(cfg, dict):
                continue
            frameworks[key] = _normalize_one_framework(cfg, base)
    for name, target in (base.get('role_daily_targets') or {}).items():
        if is_skipped_appraisal_role(name):
            continue
        frameworks.setdefault(
            name,
            _normalize_one_framework({'daily_target': target}, base),
        )
    return dict(sorted(frameworks.items(), key=lambda item: item[0].lower()))


SCORING_KEYS = (
    'basic_pay',
    'daily_target',
    'manager_daily_target',
    'role_daily_targets',
    'role_frameworks',
    'year_end_increment',
    'working_days',
    'four_star_month_min_avg',
    'four_star_months_required',
    'annual_avg_required',
    'bonus_min_stars',
    'bonus_cap',
    'daily_star_bands',
    'monthly_bonus_bands',
    'sales_basis',
    'status_labels',
)


def scoring_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(data.get(key)) for key in SCORING_KEYS}


def _parse_iso_date(value) -> Any:
    raw = str(value or '')[:10]
    if len(raw) != 10:
        return None
    try:
        return _dt.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None


def _normalize_versions(raw: Any) -> list[dict[str, Any]]:
    rows = raw.get('versions') if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        return []
    versions = []
    for row in rows[-50:]:
        if not isinstance(row, dict):
            continue
        snapshot = row.get('snapshot')
        versions.append({
            'id': _int(row.get('id'), len(versions) + 1),
            'effective_from': str(row.get('effective_from') or '')[:10],
            'effective_until': str(row.get('effective_until') or '')[:10] or None,
            'saved_at': str(row.get('saved_at') or ''),
            'saved_by': str(row.get('saved_by') or ''),
            'reason': str(row.get('reason') or '')[:500],
            'role_daily_targets': row.get('role_daily_targets')
            if isinstance(row.get('role_daily_targets'), dict)
            else {},
            'role_frameworks': row.get('role_frameworks')
            if isinstance(row.get('role_frameworks'), dict)
            else {},
            'daily_target': _float(row.get('daily_target'), 0),
            'year_end_increment': _float(row.get('year_end_increment'), 0),
            'snapshot': snapshot if isinstance(snapshot, dict) else scoring_snapshot(row),
        })
    return versions


def template_at_date(template: dict[str, Any] | None, on_date) -> dict[str, Any]:
    """Return the scoring rules that were in force on on_date."""
    data = copy.deepcopy(template or load_template())
    if on_date is None:
        return data
    if isinstance(on_date, _dt):
        on_date = on_date.date()
    elif not isinstance(on_date, _date):
        return data
    active_from = _parse_iso_date(data.get('active_from'))
    if active_from is None or on_date >= active_from:
        return data
    for row in reversed(list(data.get('versions') or [])):
        start = _parse_iso_date(row.get('effective_from'))
        until = _parse_iso_date(row.get('effective_until'))
        if start and on_date < start:
            continue
        if until and on_date >= until:
            continue
        snapshot = row.get('snapshot')
        if not isinstance(snapshot, dict):
            continue
        merged = copy.deepcopy(data)
        for key, value in snapshot.items():
            merged[key] = copy.deepcopy(value)
        return merged
    return data


def preview_for_role(template: dict[str, Any], role_name: str) -> dict[str, Any]:
    applied = template_for_role(template, role_name)
    bands = applied.get('daily_star_bands') or []
    four = next((b for b in bands if abs(_float(b.get('stars'), 0) - 4) < 0.01), None)
    five = next((b for b in bands if abs(_float(b.get('stars'), 0) - 5) < 0.01), None)
    return {
        'role': role_name,
        'daily_target': applied.get('daily_target'),
        'four_star_target': _float((four or {}).get('min'), applied.get('daily_target')),
        'five_star_target': _float((five or {}).get('min'), 0) or None,
        'basic_pay': applied.get('basic_pay'),
        'year_end_increment': applied.get('year_end_increment'),
        'working_days': applied.get('working_days'),
        'four_star_month_min_avg': applied.get('four_star_month_min_avg'),
        'four_star_months_required': applied.get('four_star_months_required'),
        'annual_avg_required': applied.get('annual_avg_required'),
        'sales_basis': applied.get('sales_basis') or 'posted_net',
    }


def template_for_role(template: dict[str, Any] | None, role_name: str) -> dict[str, Any]:
    data = copy.deepcopy(template or load_template())
    name = (role_name or '').strip()
    if is_skipped_appraisal_role(name):
        return apply_daily_target(data, 0)
    frameworks = data.get('role_frameworks') or {}
    framework = frameworks.get(name)
    if isinstance(framework, dict):
        for key in (
            'basic_pay',
            'year_end_increment',
            'working_days',
            'four_star_month_min_avg',
            'four_star_months_required',
            'annual_avg_required',
        ):
            if key in framework and framework[key] is not None:
                data[key] = framework[key]
        if framework.get('monthly_bonus_bands'):
            data['monthly_bonus_bands'] = copy.deepcopy(framework['monthly_bonus_bands'])
        if framework.get('daily_star_bands'):
            data['daily_star_bands'] = copy.deepcopy(framework['daily_star_bands'])
        target = _float(framework.get('daily_target'), resolve_role_daily_target(data, name))
        return apply_daily_target(data, target)
    return apply_daily_target(data, resolve_role_daily_target(data, name))


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
    if 'bonus_min_stars' in raw:
        data['bonus_min_stars'] = max(0, _float(raw['bonus_min_stars'], 4))
    if 'bonus_cap' in raw:
        data['bonus_cap'] = max(0, _float(raw['bonus_cap'], 10000))
    if 'contract_line' in raw:
        data['contract_line'] = str(raw.get('contract_line') or data['contract_line'])
    if 'bonus_policy_line' in raw:
        data['bonus_policy_line'] = str(raw.get('bonus_policy_line') or data['bonus_policy_line'])
    if 'show_year_end_increment' in raw:
        data['show_year_end_increment'] = bool(raw.get('show_year_end_increment'))
    if 'sales_basis' in raw:
        basis = str(raw.get('sales_basis') or 'posted_net').strip()
        data['sales_basis'] = basis if basis else 'posted_net'
    labels = raw.get('status_labels')
    if isinstance(labels, dict) and labels:
        merged = dict(data['status_labels'])
        for key, value in labels.items():
            merged[str(key)] = str(value or '')
        data['status_labels'] = merged

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
    data['role_frameworks'] = _normalize_role_frameworks(raw, data)
    for name, framework in data['role_frameworks'].items():
        data['role_daily_targets'][name] = _float(
            framework.get('daily_target'),
            data['role_daily_targets'].get(name, data['daily_target']),
        )
    data['versions'] = _normalize_versions(raw)
    if raw.get('change_reason') is not None:
        data['change_reason'] = str(raw.get('change_reason') or '')[:500]
    if raw.get('effective_from'):
        data['effective_from'] = str(raw.get('effective_from'))[:10]
    if raw.get('active_from'):
        data['active_from'] = str(raw.get('active_from'))[:10]
    if raw.get('last_change_reason') is not None:
        data['last_change_reason'] = str(raw.get('last_change_reason') or '')[:500]

    return data


def _validate_star_bands(bands: list[dict[str, Any]], *, label: str = 'Daily star') -> None:
    if not bands:
        raise PolicyError(f'{label} bands cannot be empty.')
    mins = [b['min'] for b in bands]
    if len(mins) != len(set(mins)):
        raise PolicyError(f'{label} band minimums must be unique.')
    star_order = sorted(bands, key=lambda b: _float(b.get('stars'), 0))
    for previous, current in zip(star_order, star_order[1:]):
        if _float(current.get('min'), 0) < _float(previous.get('min'), 0):
            raise PolicyError(
                f'{label}: higher star bands cannot start below lower star bands.'
            )


def _validate_bonus_bands(
    bands: list[dict[str, Any]],
    *,
    label: str = 'Monthly bonus',
    min_stars: float = 4.0,
    cap: float = 10000.0,
) -> None:
    if not bands:
        raise PolicyError(f'{label} bands cannot be empty.')
    mins = [b['min'] for b in bands]
    if len(mins) != len(set(mins)):
        raise PolicyError(f'{label} band minimums must be unique.')
    for band in bands:
        bonus = _float(band.get('bonus'), 0)
        stars = _float(band.get('stars'), 0)
        if bonus < 0:
            raise PolicyError(f'{label} amounts cannot be negative.')
        if stars < min_stars and bonus > 0:
            raise PolicyError(
                f'{label}: cash bonus starts at {min_stars:g}★. '
                f'Set bonus to 0 for bands below that (got {stars:g}★ → KES {bonus:g}).'
            )
        if cap > 0 and bonus > cap:
            raise PolicyError(
                f'{label}: bonus cannot exceed the KES {cap:g} cap (got KES {bonus:g}).'
            )


def validate_template(template: dict[str, Any]) -> dict[str, Any]:
    data = normalize_template(template)
    _validate_star_bands(data['daily_star_bands'])
    min_stars = _float(data.get('bonus_min_stars'), 4)
    cap = _float(data.get('bonus_cap'), 10000)
    _validate_bonus_bands(
        data['monthly_bonus_bands'],
        min_stars=min_stars,
        cap=cap,
    )
    if data['daily_target'] <= 0:
        raise PolicyError('Daily target must be greater than zero.')
    if data['year_end_increment'] < 0:
        raise PolicyError('Annual increment cannot be negative.')
    if data['four_star_months_required'] > 12:
        raise PolicyError('Required 4-star months cannot exceed 12.')
    for name, framework in (data.get('role_frameworks') or {}).items():
        if _float(framework.get('daily_target'), 0) <= 0:
            raise PolicyError(f'{name}: daily target must be greater than zero.')
        if _float(framework.get('year_end_increment'), 0) < 0:
            raise PolicyError(f'{name}: annual increment cannot be negative.')
        if framework.get('daily_star_bands'):
            _validate_star_bands(framework['daily_star_bands'], label=f'{name} daily star')
        if framework.get('monthly_bonus_bands'):
            _validate_bonus_bands(
                framework['monthly_bonus_bands'],
                label=f'{name} monthly bonus',
                min_stars=min_stars,
                cap=cap,
            )
    return data


def greet_when_no_sticky_notes() -> bool:
    return bool(SettingsService.get(MODULE, 'greet_when_no_sticky_notes', default=True))


def show_on_home() -> bool:
    return bool(SettingsService.get(MODULE, 'show_on_home', default=True))


def staff_facing() -> bool:
    """When False, hide Target delivery from staff nav/home (sellable package toggle)."""
    return bool(SettingsService.get(MODULE, 'staff_facing', default=True))


def load_template() -> dict[str, Any]:
    stored = SettingsService.get(MODULE, TEMPLATE_KEY, default=None)
    return normalize_template(stored)


def save_template(raw: dict[str, Any], *, user=None, request=None) -> dict[str, Any]:
    previous = load_template()
    data = validate_template(raw)
    reason = str(raw.get('change_reason') or data.pop('change_reason', '') or '')[:500]
    effective_from = str(raw.get('effective_from') or data.pop('effective_from', '') or '')[:10]
    if not effective_from:
        effective_from = timezone.localdate().isoformat()
    incoming_from = _parse_iso_date(effective_from)
    previous_from = _parse_iso_date(previous.get('active_from'))
    if incoming_from and previous_from and incoming_from < previous_from:
        raise PolicyError('Effective date cannot precede the previous configuration.')
    versions = list(previous.get('versions') or [])
    if scoring_snapshot(previous) != scoring_snapshot(data):
        versions.append({
            'id': (versions[-1]['id'] + 1) if versions else 1,
            'effective_from': previous.get('active_from') or '',
            'effective_until': effective_from,
            'saved_at': timezone.now().isoformat(),
            'saved_by': getattr(user, 'username', '') or '',
            'reason': previous.get('last_change_reason') or reason,
            'role_daily_targets': copy.deepcopy(previous.get('role_daily_targets') or {}),
            'role_frameworks': copy.deepcopy(previous.get('role_frameworks') or {}),
            'daily_target': previous.get('daily_target'),
            'year_end_increment': previous.get('year_end_increment'),
            'snapshot': scoring_snapshot(previous),
        })
    data['versions'] = versions[-50:]
    data['active_from'] = effective_from
    data['last_change_reason'] = reason
    data.pop('change_reason', None)
    data.pop('effective_from', None)
    SettingsService.set(MODULE, TEMPLATE_KEY, data, user=user)
    flags = {}
    if 'greet_when_no_sticky_notes' in raw:
        flags['greet_when_no_sticky_notes'] = bool(raw['greet_when_no_sticky_notes'])
    if 'show_on_home' in raw:
        flags['show_on_home'] = bool(raw['show_on_home'])
    if 'staff_facing' in raw:
        flags['staff_facing'] = bool(raw['staff_facing'])
    if flags:
        SettingsService.set_many(MODULE, flags, user=user)
    try:
        from accounts.models import AuditLog
        from utils.audit import log_audit

        log_audit(
            request,
            AuditLog.ACTION_UPDATE,
            None,
            module='appraisals',
            object_repr='Performance rules',
            changes=_policy_audit_changes(previous, data, reason, effective_from, user),
        )
    except Exception:
        pass
    return public_policy(data)


def _policy_audit_changes(previous, data, reason, effective_from, user) -> dict[str, Any]:
    fields = []
    for key in (
        'daily_target',
        'year_end_increment',
        'working_days',
        'four_star_month_min_avg',
        'four_star_months_required',
        'annual_avg_required',
        'basic_pay',
    ):
        old = previous.get(key)
        new = data.get(key)
        if old != new:
            fields.append({'field': key, 'previous': old, 'new': new})
    old_targets = previous.get('role_daily_targets') or {}
    new_targets = data.get('role_daily_targets') or {}
    for role in sorted(set(old_targets) | set(new_targets)):
        if old_targets.get(role) != new_targets.get(role):
            fields.append({
                'field': f'role_daily_targets.{role}',
                'previous': old_targets.get(role),
                'new': new_targets.get(role),
            })
    return {
        'admin': getattr(user, 'get_full_name', lambda: '')() or getattr(user, 'username', '') or '',
        'reason': reason,
        'effective_from': effective_from,
        'fields': fields,
        'previous_daily_target': previous.get('daily_target'),
        'daily_target': data.get('daily_target'),
        'previous_year_end_increment': previous.get('year_end_increment'),
        'year_end_increment': data.get('year_end_increment'),
        'role_daily_targets': data.get('role_daily_targets'),
    }


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
    data['role_frameworks'] = _normalize_role_frameworks(data, data)
    data['role_previews'] = {
        name: preview_for_role(data, name) for name in data['role_daily_targets']
    }
    data['greet_when_no_sticky_notes'] = greet_when_no_sticky_notes()
    data['show_on_home'] = show_on_home()
    data['staff_facing'] = staff_facing()
    return data
