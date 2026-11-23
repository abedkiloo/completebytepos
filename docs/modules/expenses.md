# expenses

## Purpose

Track store operating expenses with category taxonomy and an approve/reject/void workflow. Approved rows feed accounting journals and trading-profit reports when the category allows it.

## Key models

| Model | Role |
|-------|------|
| `ExpenseCategory` | Named category; `include_in_trading_profit` gates P&L |
| `Expense` | Voucher: amount, date occurred, status, payment method, branch |

## Public entry points

- `ExpenseService.approve_expense` / `reject_expense` / `resubmit_expense` / `void_expense`
- `ExpenseCategoryService.delete_unused_category`
- HTTP: `/api/expenses/` (expenses + categories)

## Bounds & invariants

- `amount` ≥ 0.01 (`Decimal`, 2 dp); unique auto `expense_number`.
- Creates force `pending`; approve/reject/void only via service transitions.
- Approver ≠ maker; past-dated checks need admin override.
- An employee claim (`is_claim`, feature `expenses.employee_claims`) is filed by staff with `expenses.claim`. It appears in Expenses. A manager with `expenses.claim_approve` decides a staff claim. A director decides a manager's claim. The claimant cannot decide it. Admin `expenses.approve` does not decide a claim. Amount 0.01–99999999.99. The day is today back through 30 days. Description 1–500 characters.
- Approved/paid rows locked from casual edit/delete; void reverses journals.

## Audit

`AuditedModelViewSetMixin` (`module=expenses`); approve/void also touch accounting.

## Gaps

- Journal create failure on approve is logged but does not roll back status.
- Public API docstrings partially upgraded (services first).
