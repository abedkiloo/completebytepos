# reports

## Purpose

Aggregated dashboards/exports over sales, stock, expenses, and income. No own domain tables — reads other apps via scoped query helpers.

## Key models

*(none)*

## Public APIs

Prefix: `/api/reports/`

## Bounds & invariants

- Sale reports use posted-sale scope helpers, not raw drafts.
- Feature flags/labels from module settings gate/annotate responses.
- Date filters should use inclusive start/end helpers from `services`.

## Audit

Read-only; no domain mutations. Export endpoints may still log access if required by policy.

## Gaps

- Public API docstrings: **done** for ``sale_scope``, ``services`` (``resolve_period``, dashboard), and view helpers ``request_date_bounds`` / ``sale_report_queryset``; export/specialized report modules still partial.
