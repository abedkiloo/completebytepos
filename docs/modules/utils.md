# utils

## Purpose

Shared cross-app helpers: audit logging/mixins, pagination, phone normalization, PDF helpers, money format, test bases.

## Key models

*(none)*

## Public entry points

- `utils.audit` / `utils.audit_helpers.log_domain_event` / `AuditedModelViewSetMixin`
- Branding, PDF, phone, pagination helpers under `be/utils/`

## Bounds & invariants

- Material writes should go through audit helpers / audited mixins.
- Prefer Decimal/phone helpers over ad-hoc formatting.
- Audit payloads must not store secrets (tokens, passwords).

## Gaps

- Public API docstrings: **done** for ``audit.py``, ``audit_helpers.py``, and ``audit_mixin.py`` entry points; ``audit_events`` and other utils modules still partial.
