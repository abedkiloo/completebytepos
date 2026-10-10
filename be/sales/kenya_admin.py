"""Kenya county / sub-county / ward lookup for customer registration."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / 'data' / 'kenya_admin_units.json'

DEFAULT_COUNTY = 'Nairobi'
DEFAULT_SUB_COUNTY = 'Starehe'
DEFAULT_WARD = 'Landimawe'


def _normalize_key(value: str) -> str:
    text = (value or '').strip().lower()
    text = text.replace("'", '').replace('’', '')
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


@lru_cache(maxsize=1)
def load_admin_tree() -> dict[str, dict[str, list[str]]]:
    with _DATA_PATH.open(encoding='utf-8') as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError('kenya_admin_units.json must be a county → sub-county → wards object')
    return raw


def county_names() -> list[str]:
    return sorted(load_admin_tree().keys())


def sub_county_names(county: str) -> list[str]:
    tree = load_admin_tree()
    canonical = resolve_county(county)
    if not canonical:
        return []
    return sorted(tree[canonical].keys())


def ward_names(county: str, sub_county: str) -> list[str]:
    tree = load_admin_tree()
    canonical_county = resolve_county(county)
    if not canonical_county:
        return []
    canonical_sub = resolve_sub_county(canonical_county, sub_county)
    if not canonical_sub:
        return []
    return list(tree[canonical_county][canonical_sub])


def resolve_county(value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    target = _normalize_key(str(value))
    for name in load_admin_tree().keys():
        if _normalize_key(name) == target:
            return name
    return None


def resolve_sub_county(county: str, value: str | None) -> str | None:
    canonical_county = resolve_county(county)
    if not canonical_county or not value or not str(value).strip():
        return None
    target = _normalize_key(str(value))
    for name in load_admin_tree()[canonical_county].keys():
        if _normalize_key(name) == target:
            return name
    return None


def resolve_ward(county: str, sub_county: str, value: str | None) -> str | None:
    canonical_county = resolve_county(county)
    canonical_sub = resolve_sub_county(canonical_county or county, sub_county)
    if not canonical_county or not canonical_sub or not value or not str(value).strip():
        return None
    target = _normalize_key(str(value))
    for name in load_admin_tree()[canonical_county][canonical_sub]:
        if _normalize_key(name) == target:
            return name
    return None


def _first_sub_county(county: str) -> str:
    names = sub_county_names(county)
    if county == DEFAULT_COUNTY and DEFAULT_SUB_COUNTY in names:
        return DEFAULT_SUB_COUNTY
    return names[0] if names else DEFAULT_SUB_COUNTY


def _first_ward(county: str, sub_county: str) -> str:
    names = ward_names(county, sub_county)
    if (
        county == DEFAULT_COUNTY
        and sub_county == DEFAULT_SUB_COUNTY
        and DEFAULT_WARD in names
    ):
        return DEFAULT_WARD
    return names[0] if names else DEFAULT_WARD


def apply_location_defaults(
    county: str | None,
    sub_county: str | None,
    ward: str | None,
) -> tuple[str, str, str]:
    """
    Fill blank/invalid levels so registration never gets stuck on location.

    Prefer the caller's county when valid; otherwise Nairobi defaults.
    Sub-county / ward fall back to the first valid unit under the chosen county.
    """
    canonical_county = resolve_county(county) or DEFAULT_COUNTY
    canonical_sub = resolve_sub_county(canonical_county, sub_county)
    if not canonical_sub:
        canonical_sub = _first_sub_county(canonical_county)
    canonical_ward = resolve_ward(canonical_county, canonical_sub, ward)
    if not canonical_ward:
        canonical_ward = _first_ward(canonical_county, canonical_sub)
    return canonical_county, canonical_sub, canonical_ward


def validate_admin_location(
    county: str | None,
    sub_county: str | None,
    ward: str | None,
    *,
    apply_defaults: bool = False,
) -> tuple[str, str, str] | dict[str, str]:
    """
    Return canonical (county, sub_county, ward) or field errors dict.

    When apply_defaults=True (customer create), incomplete or mismatched
    values are repaired instead of rejecting the request.
    """
    if apply_defaults:
        return apply_location_defaults(county, sub_county, ward)

    errors: dict[str, str] = {}
    if not county or not str(county).strip():
        errors['county'] = 'Select a county.'
    if not sub_county or not str(sub_county).strip():
        errors['sub_county'] = 'Select a sub-county.'
    if not ward or not str(ward).strip():
        errors['ward'] = 'Select a ward.'
    if errors:
        return errors

    canonical_county = resolve_county(county)
    if not canonical_county:
        return {'county': 'Select a valid Kenyan county.'}

    canonical_sub = resolve_sub_county(canonical_county, sub_county)
    if not canonical_sub:
        return {'sub_county': 'Select a sub-county in this county.'}

    canonical_ward = resolve_ward(canonical_county, canonical_sub, ward)
    if not canonical_ward:
        return {'ward': 'Select a ward in this sub-county.'}

    return canonical_county, canonical_sub, canonical_ward


def admin_units_payload() -> dict:
    return {
        'defaults': {
            'county': DEFAULT_COUNTY,
            'sub_county': DEFAULT_SUB_COUNTY,
            'ward': DEFAULT_WARD,
        },
        'counties': load_admin_tree(),
    }
