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

- [x] Settle debt on Android against API
- [x] Permission `customers.update` gated
- [x] ≥98% coverage on customers feature package

**Flutter coverage:** ≥98% on `lib/features/customers` (98.59%)

```bash
cd mobile
flutter analyze
flutter test --coverage
dart run tools/check_coverage.dart --min=98 --paths=lib/features/customers
```
