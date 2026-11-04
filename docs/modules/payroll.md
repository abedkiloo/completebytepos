# payroll

## Purpose

Monthly payroll: pay component catalog, role packages, per-employee overrides, run lifecycle (calculate → submit → approve/lock), and payslip PDF/self-service. Statutory rules exist but stay off until `PayrollSettings.statutory_enabled`.

## Key models

| Model | Role |
|-------|------|
| `PayrollSettings` | Currency, pay day (1–28), statutory/bonus toggles, letterhead |
| `PayComponent` | Earning/deduction/employer definitions |
| `RolePayPackage` / lines | Default package for an accounts `Role` |
| `EmployeePayAssignment` | Dated personal overrides |
| `PayrollRun` | One `(tenant, year, month)` cycle |
| `Payslip` / `PayslipLine` | Frozen snapshot for a run |

## Public APIs

Prefix: `/api/payroll/` — settings, components, packages, assignments, runs, payslips, `me/pay/`, `me/payslips/`, year report.

## Bounds & invariants

- One run per tenant/year/month.
- Status: `draft` → `calculated` → `pending_approval` → `locked` (or `cancelled`); locked is immutable.
- Money is `Decimal` (never float). Pay day ∈ [1, 28].
- Self-service needs employee linked to user email (`employee_for_user`).
- Estimate pay does **not** include run-only adapters (full statutory/loan) — locked payslips do.

## Audit

CRUD ViewSets use `AuditedModelViewSetMixin` (`module=payroll`). Run lifecycle and settings use `log_audit` / `log_domain_event`.

## Gaps

- Statutory band engine is largely placeholder until enabled.
- Attendance/loan adapters are thin stubs — verify before production reliance.
