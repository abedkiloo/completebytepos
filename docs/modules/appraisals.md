# appraisals

## Purpose

Sales-target “stars” scoring (daily/monthly/year-end) from posted net sales and collections; optional year-end salary increment that can update `Employee.salary`.

## Key models

| Model | Role |
|-------|------|
| `AppraisalSalaryIncrement` | Per `(user, year)` eligibility and approve/reject decision |

Policy JSON lives in module settings (`appraisals.template`), not a dedicated model.

## Public APIs

Prefix: `/api/appraisals/` — `policy/`, `me/`, `team/`, `increments/`, `increments/<id>/decision/`.

## Bounds & invariants

- Year query ∈ [2000, 2100] when provided.
- Cash bonus gated by collection ratio (default 80%).
- Approve sets `Employee.salary = new_basic` only when qualified and not already approved.
- Policy version history retained (last ~50).

## Audit

`log_audit` on policy save and increment decide.

## Gaps

- Increment path is not maker-checker `PendingChange`.
- Approve does not recalculate payroll runs.
