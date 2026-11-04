# accounts

## Purpose

Identity and access for the POS API: Django users, legacy role strings plus custom `Role`/`Permission` RBAC, and the system-wide append-only `AuditLog`. Owns login/logout, password-change enforcement, and permission checks used by every other module.

## Key models

| Model | Role |
|-------|------|
| `Permission` | Granular `(module, action)` grants |
| `Role` | Named permission set; system roles cannot be deleted |
| `UserProfile` | Extends `User` with legacy role, optional `custom_role`, `must_change_password` |
| `AuditLog` | Immutable who/what/when ledger (updates raise) |

## Public APIs

Prefix: `/api/accounts/`

- `permissions/`, `roles/`, `users/`, `auth/` (login/logout/me)
- `audit-logs/` (+ `facets/`) — filter by day, time, user, module, action

## Invariants

- Super admin bypasses permission checks.
- `AuditLog` rows are immutable after create.
- `must_change_password` blocks most API traffic until changed.
- Dual auth (`UserProfile.role` vs `custom_role`) must stay consistent.

## Audit

Roles use `AuditedModelViewSetMixin`. Users/auth use explicit `log_domain_event` / `log_audit` for create/update/delete/login/logout/password/role assign.

## Gaps

- Keep MODULE/ACTION catalogs in sync with new permission grants.
- Prefer deactivating users over hard delete.
