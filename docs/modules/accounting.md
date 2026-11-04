# accounting

## Purpose

Chart of accounts and double-entry journals/transactions for books. Source documents (sales, expenses, income, stock) create journals via services.

## Key models

| Model | Role |
|-------|------|
| `AccountType` / `Account` | Chart of accounts |
| `JournalEntry` / `Transaction` | Balanced debit/credit lines |

## Public APIs

Prefix: `/api/accounting/`

## Bounds & invariants

- Journal amounts ≥ 0.01; account balances update from debit/credit vs normal balance.
- Entries PROTECT accounts; `reference_type` / `reference_id` link back to source docs.
- Reversals create offsetting journals — do not delete posted history.

## Audit

Journal create/reverse should be traceable from source module audits + accounting rows.

## Gaps

- Public API docstrings: **done** for `models.py`, `services.py` (journal create helpers), and `reversal.py`; views/reports still partial.
