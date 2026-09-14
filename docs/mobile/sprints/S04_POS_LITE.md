# S04 — Store POS lite

**Paste after `MASTER_PROMPT.md`.**

## Goal

Cashier can search products, build a cart, take payment (cash/mpesa/card/other), and view a digital receipt — using real sales API; offline queue for safe drafts if online checkout is required for stock.

## In scope

- Product search + barcode input hook
- Cart (add/update/remove)
- Customer attach (respect module flags if exposed by API)
- Checkout calling existing sale/checkout endpoints
- Success receipt screen (print later optional)
- Honor stock validation errors from backend

## Out of scope

- Full billing POS holdings complexity (can BACKLOG “holdings v2”)
- Refunds (S06 or later)
- Field agent orders (S08)

## UX mental model

- Search → Cart → Pay → Done (linear confidence)
- Sticky total + primary Pay CTA
- Confirm leave if cart dirty

## Tests (TDD)

- Unit: cart totals, tax/discount if applicable
- Widget: empty cart CTA
- Widget: pay button disabled until valid
- Mock API: checkout success + insufficient stock error

## Backend

- Reuse `/api/sales/` create/checkout; no schema change unless bugfix (with tests)

## Definition of Done

- [x] Android smoke: complete one cash sale against API
- [x] ≥98% on POS feature package
- [x] Module flags that block features don’t crash app

### Sprint notes (S04 completion)

**Coverage:** `98.90%` on `lib/features/pos` (537/543).

```bash
dart run tools/check_coverage.dart --min=98 --paths=lib/features/pos
```

**Flow:** Search/scan → cart → Pay sheet → `POST /api/sales/` (Idempotency-Key) → receipt. Offline → outbox enqueue + “waiting to sync” receipt (never fakes success).

**Flags:** `PosSettings.fromApis` — `require_customer`, enabled payment methods; settings load failure → safe defaults (no crash). Wallet in store methods is ignored as a chip (maps to `use_wallet` later / S05).

**Android smoke:** `flutter run -d <android> --dart-define=API_BASE_URL=http://10.0.2.2:8000/api` → New sale → search product → Pay cash.

**Deferred:** Holdings v2 → `BACKLOG.md`.
