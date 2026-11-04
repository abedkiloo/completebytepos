# employees

## Purpose

HR roster for staff: identity, employment, optional login link, salary/bank fields used by payroll and appraisals.

## Key models

| Model | Role |
|-------|------|
| `Employee` | Staff code, names, position, department, hire date, status, optional salary/bank, optional 1:1 `user` |

## Public APIs

Prefix: `/api/employees/` — CRUD, `statistics/`, `linkable-users/`, `from-user/`.

## Bounds & invariants

- `employee_id` unique; at most one employee per user; salary ≥ 0.
- Feature flags can 403 create/edit/delete/stats.
- List is not tenant-scoped despite optional `tenant` FK.

## Audit

`AuditedModelViewSetMixin` (`module=employees`); create sets `created_by`.

## Gaps

- Soft-delete is status-only; hard delete when flag allows.
- Salary visibility depends on module settings seeding.
