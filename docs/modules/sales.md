# sales

## Purpose

POS/billing domain: customers (duka identity, wallet/debt), holdings → approval → completed sales, refunds/rollback/unvoid, invoices/payments, daily sales, and debt collection. Wallet unpaid balance is the customer debt source of truth for underpaid sales.

## Key models

| Model | Role |
|-------|------|
| `Customer` | Duka profile; negative `wallet_balance` = owes us |
| `Sale` / `SaleItem` | Lifecycle holding → pending_approval → completed/cancelled |
| `SaleRefund` | Void/partial refund |
| `Invoice` / `Payment` | Credit/billing path |
| `CustomerWalletTransaction` | Wallet ledger |

## Public entry points

- `SaleService.create_sale` / holding / checkout / complete paths
- `sale_completion_approval.*`, `sale_debt_sync.*`, refunds/rollback/unvoid
- HTTP: `/api/sales/` (sales, customers, invoices, payments)

## Bounds & invariants

- Negative wallet = debt; unpaid sale posts `source_type='debt'`.
- Return-for-correction reverses wallet **and** invalidates old debt rows.
- Returned sales must be edited before resubmit.
- Unit price must not go below catalog selling price.
- All money is `Decimal`. Customer search covers name/owner/contact/code/email/phone.

## Audit

ViewSets use audited mixin. Domain events: checkout, holding, refund, rollback, unvoid, date correct.

## Gaps

- Historical desync repaired via management commands (`repair_sale_debt`, etc.).
- Prefer service paths for new work; avoid ad-hoc SQL.
