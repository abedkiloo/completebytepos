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

- [ ] End-to-end on Android: agent submit → dispatcher assign
- [ ] ≥98% coverage new BE + FE packages
- [ ] Push notification stub OK if provider not ready (interface + fake) — real push can BACKLOG
