# S09 — Delivery run, map-first stop UI, POD

**Paste after `MASTER_PROMPT.md`.**

## Goal

Delivery agent completes routes stop-by-stop. **Each stop opens map + photo gallery first**, then lines, collect, and proof of delivery. Best-in-class field clarity.

## In scope

### Backend

- Route / stop entities or derive stops from assigned FieldOrders
- Stop status machine: pending → arrived → delivering → collected → completed / failed
- `DeliveryLineResult` per SKU: delivered qty, returned qty
- `ProofOfDelivery`: signature image, photo, notes, lat/lng, timestamp
- Optional: propose corrected pin (pending manager approval)

### Flutter — Delivery agent

- Today’s route list (ordered)
- **Stop screen layout (mandatory order):**
  1. Full-width map + pin + Open in Maps
  2. Photo carousel + landmark
  3. Customer / call button
  4. Line items actions
  5. Collect money (cash / mark debt / defer STK to S10)
  6. POD capture → Complete → next stop
- Partial delivery + returns update stock via API
- Offline: allow POD capture queued if policy says so (document)

## Out of scope

- STK Push (S10) — show “Record cash / debt” only or stub “Request M-Pesa”
- Route optimization algorithms

## UX mental model

- “Recognize the place → do the work → prove it → next”
- One primary CTA at a time (Arrive → Start delivery → Complete stop)
- Motion: horizontal between stops; vertical scroll within stop

## Tests (TDD)

- BE: cannot complete stop without POD if config requires
- BE: partial quantities validation
- Widget: map/photos render above lines (finders by key)
- Widget: Complete disabled until required POD fields set
- Unit: next-stop selection

## Definition of Done

- [ ] Android demo: 2-stop route completed with photos visible
- [ ] ≥98% coverage delivery packages (BE+FE)
- [ ] UX review notes against `UX_MENTAL_MODELS.md` section F
