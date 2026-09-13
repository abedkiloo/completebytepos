# S06 — Sales history, refunds lite, daily sales

**Paste after `MASTER_PROMPT.md`.**

## Goal

Cashiers/managers browse sales history; managers/admins with `sales.daily_sales` use Daily Sales tracker (paid vs debt) and open customer day context where API allows.

## In scope

- Sales history list + filters (date, method, search)
- Sale detail / receipt
- Refund/void entry if user has `sales.refund` (call existing API)
- Daily Sales screens gated by `sales.daily_sales`
- Customer day summary navigation if backend daily customer endpoint exists

## Out of scope

- Agent flows
- Export PDF on device (BACKLOG)

## UX mental model

- History: find → open → act
- Daily Sales: pick day → trust summary cards → drill row
- No Daily Sales entry in nav without permission (match web)

## Tests (TDD)

- Unit: payment status classification display helpers (paid/debt/partial)
- Widget: daily sales hidden without permission
- Widget: day chips / previous-next day
- Mock API: debt filter tab

## Backend

- Reuse `/api/sales/daily/` and `/api/sales/daily/customer/<id>/`
- Ensure mobile auth users with/without permission covered in BE tests if changing perms

## Definition of Done

- [ ] Android: history + daily sales smoke for admin
- [ ] Manager without `daily_sales` cannot open route
- [ ] ≥98% on history + daily_sales feature packages
