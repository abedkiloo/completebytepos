# transfers

## Purpose

Move money between bank accounts and/or cash with a numbered transfer document and status machine.

## Key models

| Model | Role |
|-------|------|
| `MoneyTransfer` | From/to accounts, amount, status, unique `transfer_number` |

## Public APIs

Prefix: `/api/transfers/`

## Bounds & invariants

- Amount ≥ 0.01; unique `transfer_number`.
- Balance side effects only when status is `completed`.
- Incomplete/cancelled transfers must not mutate ledger balances.

## Audit

Domain audit on complete/cancel paths.

## Gaps

- Public API docstrings: **done** for `models.py` and `services.py` (views/serializers still partial).
