# S08 — Field orders & store dispatch

**Paste after `MASTER_PROMPT.md`.**

## Goal

Agent builds an order tied to a **CustomerSite** (pin + photos), submits to store; dispatcher packs and assigns a delivery agent. Store users see site map/photos for context.

## In scope

### Backend

- `FieldOrder` (+ lines) statuses: draft → submitted → packing → ready → out_for_delivery → done/cancelled
- Link to CustomerSite + SiteMedia
- Reject submit without site pin + media
- Dispatch board APIs: list submitted, mark packed, assign delivery agent
- Stock reservation or explicit “allocate on pack” policy (document decision)

### Flutter — Agent

- Order cart from catalog (reuse POS cart patterns)
- Review screen shows site map thumbnail + photo strip
- Submit order

### Flutter — Dispatcher

- Queue of orders
- Detail: map + photos + lines
- Pack + assign delivery agent

## Out of scope

- On-road POD (S09)
- STK payments (S10)

## UX mental model

- Agent: “I’m sending work to the store”
- Dispatcher: “I’m preparing what the driver will take”
- Always show site visuals before packing confirm

## Tests (TDD)

- BE: state machine transitions illegal paths fail
- BE: submit without site fails
- FE: submit button validation
- FE: dispatcher assign requires agent selected

## Definition of Done

- [x] End-to-end on Android: agent submit → dispatcher assign
- [x] ≥98% coverage new BE + FE packages
- [x] Push notification stub OK if provider not ready (interface + fake) — real push can BACKLOG

### Sprint notes (2026-09-14)

- Stock policy: **allocate on pack** (`stock_allocated=True` on pack; no inventory ledger yet).
- BE: `FieldOrder` / `FieldOrderLine`, agent APIs under `/api/agents/field-orders/`, dispatch board `/api/dispatch/*`, `FakePushNotifier` / `NoOpPushNotifier`.
- FE: `lib/features/field_orders/` (cart → review → submit), `lib/features/dispatch/` (queue → pack/assign), `lib/core/notifications/push_notifier.dart`.
- Coverage: BE agents+dispatch **99.6%** (S08 modules **100%**); FE field_orders+dispatch+notifications **99.26%**.
- Android smoke: agent home / More → New field order → add line → Review → Submit to store; dispatcher / manager with `dispatch.*` → Dispatch queue → open order (map+photos first) → Pack → select agent → Assign.