# services

## Purpose

Shared service base class and inclusive datetime filter helpers for list/report queries. Business invariants stay in app services, not views.

## Key models

*(none)*

## Public entry points

- `services.base.BaseService`
- Inclusive start/end date helpers used by reports and list filters

## Bounds & invariants

- Date bounds use inclusive start/end helpers for reporting consistency.
- Views stay thin; mutations live in app `services.py`.

## Gaps

- Public API docstrings: **done** for ``base.py`` and ``datetime_filters.py``; keep aligned with ``be/STRUCTURE.md`` service rules when adding new shared helpers.
