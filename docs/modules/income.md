# income

## Purpose

Record non-sale income (other receipts) with categories and the same style of approval workflow as expenses.

## Key models

| Model | Role |
|-------|------|
| `IncomeCategory` | Taxonomy for other income |
| `Income` | Receipt row with amount, status, unique `income_number` |

## Public APIs

Prefix: `/api/income/`

## Bounds & invariants

- Amount ≥ 0.01; status flows pending → approved/rejected/received/voided.
- Unique auto `income_number`.
- Approved rows should not be casually edited; void reverses books when posted.

## Audit

Audited ViewSet / domain events on status transitions (see `be/income/`).

## Gaps

- Public API docstrings: **done** for `models.py` and `services.py` (views/serializers still partial).
