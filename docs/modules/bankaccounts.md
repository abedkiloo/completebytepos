# bankaccounts

## Purpose

Maintain bank/cash ledger accounts and deposit/withdrawal lines used by transfers, expenses, and reporting.

## Key models

| Model | Role |
|-------|------|
| `BankAccount` | Named account with unique `account_number` |
| `BankTransaction` | Deposit/withdrawal line affecting balance |

## Public APIs

Prefix: `/api/bank-accounts/`

## Bounds & invariants

- `account_number` unique; money uses `Decimal`.
- Balances recomputed from transactions + completed transfers — not free-form write-throughs for ops truth.
- Opening/current balances must stay consistent with ledger math.

## Audit

Mutating ViewSet paths should emit audit rows (`module=bankaccounts`).

## Gaps

- Public API docstrings: **done** for `models.py` and `services.py` (views/serializers still partial).
