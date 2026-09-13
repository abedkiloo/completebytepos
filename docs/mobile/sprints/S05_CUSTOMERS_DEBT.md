# S05 — Customers & wallet debt

**Paste after `MASTER_PROMPT.md`.**

## Goal

Manage customers on mobile and settle wallet debt (Receive payment) with the same mental model as web Debt Management / customer detail.

## In scope

- Customer list + search
- Customer create/edit (respect customer module settings when API returns flags)
- Customer detail: identity, wallet standing, recent sales lite
- Receive wallet payment flow
- Deep link from POS “add customer”

## Out of scope

- Full invoice PDF UI
- Agent map sites (S07)
- Daily sales (S06)

## UX mental model

- Detail: standing first (good / owes X)
- Settle: amount hero → method → confirm
- Success returns to detail with refreshed balance

## Tests (TDD)

- Unit: debt amount from negative wallet
- Widget: hide settle when no debt / no permission
- Mock API: receive payment success refreshes

## Backend

- Existing customers + receive-wallet-payment endpoints
- Extend only if mobile needs compact serializers (with tests)

## Definition of Done

- [ ] Settle debt on Android against API
- [ ] Permission `customers.update` gated
- [ ] ≥98% coverage on customers feature package
