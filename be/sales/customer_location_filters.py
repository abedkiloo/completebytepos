"""
Filter customer querysets by Kenya admin location and validity.

Public entry points:
    - ``apply_customer_location_filters`` — list query params
    - ``annotate_location_issue`` — issue code for one customer row

Side effects: none (read-only queryset narrowing).
"""

from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet

from sales.kenya_admin import (
    LOCATION_OK,
    classify_admin_location,
    resolve_county,
    resolve_sub_county,
    resolve_ward,
)


def annotate_location_issue(customer) -> dict[str, Any]:
    """
    Build location validity fields for a customer list/detail payload.

    Args:
        customer: ``Customer`` instance (uses ``county`` / ``sub_county`` / ``ward``).

    Returns:
        Dict with ``location_valid`` (bool) and ``location_issue`` (str code;
        empty when valid). Codes: ``missing``, ``invalid_county``,
        ``invalid_sub_county``, ``invalid_ward``.
    """
    ok, issue = classify_admin_location(
        getattr(customer, 'county', None),
        getattr(customer, 'sub_county', None),
        getattr(customer, 'ward', None),
    )
    return {
        'location_valid': ok,
        'location_issue': issue if not ok else LOCATION_OK,
    }


def _blank_admin_q() -> Q:
    """Match rows missing any of county / sub_county / ward."""
    return (
        Q(county__isnull=True)
        | Q(county__exact='')
        | Q(sub_county__isnull=True)
        | Q(sub_county__exact='')
        | Q(ward__isnull=True)
        | Q(ward__exact='')
    )


def _invalid_combo_q(queryset: QuerySet) -> Q:
    """
    OR of distinct stored triples that fail catalog validation.

    Args:
        queryset: Customer queryset already narrowed by other filters.

    Returns:
        ``Q`` matching invalid non-blank triples. Empty ``Q()`` when none.
    """
    combos = queryset.values_list('county', 'sub_county', 'ward').distinct()
    q = Q()
    found = False
    for county, sub_county, ward in combos:
        ok, _issue = classify_admin_location(county, sub_county, ward)
        if ok:
            continue
        found = True
        q |= Q(
            county=county if county is not None else '',
            sub_county=sub_county if sub_county is not None else '',
            ward=ward if ward is not None else '',
        )
    return q if found else Q(pk__in=[])


def apply_customer_location_filters(
    queryset: QuerySet,
    params: dict[str, Any] | Any,
) -> QuerySet:
    """
    Narrow customers by county / sub-county / ward and/or location validity.

    Args:
        queryset: Base ``Customer`` queryset.
        params: Request query params (dict-like). Supported keys:
            - ``county``: filter to that county (resolved to canonical, iexact).
            - ``sub_county``: requires a resolvable county context (uses
              ``county`` param when present, else any county that owns the sub).
            - ``ward``: requires county + sub_county context when possible.
            - ``location_status``: ``valid`` | ``invalid`` (includes missing
              and mismatched catalog values). Blank = no status filter.

    Returns:
        Filtered queryset. Unknown ``location_status`` values are ignored.
        Unresolvable location params yield an empty queryset (no silent broaden).

    Bounds:
        Filter strings are stripped; empty string clears that level. No page
        size change — pagination stays on the ViewSet.
    """
    get = params.get if hasattr(params, 'get') else lambda _k, _d=None: None

    county_raw = (get('county') or '').strip()
    sub_raw = (get('sub_county') or '').strip()
    ward_raw = (get('ward') or '').strip()
    status_raw = (get('location_status') or '').strip().lower()

    if county_raw:
        canonical_county = resolve_county(county_raw)
        if not canonical_county:
            return queryset.none()
        queryset = queryset.filter(county__iexact=canonical_county)
    else:
        canonical_county = None

    if sub_raw:
        if canonical_county:
            canonical_sub = resolve_sub_county(canonical_county, sub_raw)
            if not canonical_sub:
                return queryset.none()
            queryset = queryset.filter(sub_county__iexact=canonical_sub)
        else:
            # Match any county where this sub-county name resolves.
            from sales.kenya_admin import load_admin_tree

            matches: list[str] = []
            for c_name, _subs in load_admin_tree().items():
                resolved = resolve_sub_county(c_name, sub_raw)
                if resolved and resolved not in matches:
                    matches.append(resolved)
            if not matches:
                return queryset.none()
            sub_q = Q()
            for name in matches:
                sub_q |= Q(sub_county__iexact=name)
            queryset = queryset.filter(sub_q)
            canonical_sub = matches[0] if len(matches) == 1 else None
    else:
        canonical_sub = None

    if ward_raw:
        if canonical_county and (canonical_sub or sub_raw):
            sub_for_ward = canonical_sub or resolve_sub_county(canonical_county, sub_raw)
            if not sub_for_ward:
                return queryset.none()
            canonical_ward = resolve_ward(canonical_county, sub_for_ward, ward_raw)
            if not canonical_ward:
                return queryset.none()
            queryset = queryset.filter(ward__iexact=canonical_ward)
        else:
            from sales.kenya_admin import load_admin_tree

            matches: list[str] = []
            for c_name, subs in load_admin_tree().items():
                for s_name in subs.keys():
                    resolved = resolve_ward(c_name, s_name, ward_raw)
                    if resolved and resolved not in matches:
                        matches.append(resolved)
            if not matches:
                return queryset.none()
            ward_q = Q()
            for name in matches:
                ward_q |= Q(ward__iexact=name)
            queryset = queryset.filter(ward_q)

    if status_raw == 'invalid':
        blank_q = _blank_admin_q()
        # Evaluate invalid combos on the queryset *before* status filter
        # but after geographic filters so the distinct scan stays small.
        invalid_q = _invalid_combo_q(queryset)
        queryset = queryset.filter(blank_q | invalid_q)
    elif status_raw == 'valid':
        blank_q = _blank_admin_q()
        invalid_q = _invalid_combo_q(queryset.exclude(blank_q))
        queryset = queryset.exclude(blank_q).exclude(invalid_q)

    return queryset
