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

- [x] Android demo: 2-stop route completed with photos visible
- [x] ≥98% coverage delivery packages (BE+FE)
- [x] UX review notes against `UX_MENTAL_MODELS.md` section F

### Sprint notes (2026-09-14)

- **Offline POD policy:** `ALLOW_OFFLINE_POD_QUEUE=true` — clients may enqueue POD to the sync outbox when offline; server accepts the same payload on sync (`delivery/config/`).
- BE: `delivery` app — `DeliveryRoute` / `DeliveryStop` / `DeliveryLineResult` / `ProofOfDelivery` / `ProposedPinCorrection`; assign enqueues stop as `out_for_delivery`.
- FE: `lib/features/delivery/` — today’s route + map-first stop (map → photos → customer → lines → collect → POD).
- Coverage: BE `delivery` **99.1%**; FE `lib/features/delivery` **98.60%**.
- Android smoke: Delivery home → Today’s route (2 stops) → open stop (map+photos above lines) → Arrive → Start → lines/collect → POD → Complete → next stop.

### UX review — section F

| F rule | Implementation |
|--------|----------------|
| Map (pin) + Open in Maps | `del_stop_map` + `del_open_maps` first |
| Photo carousel + landmark | `del_stop_photos` then landmark |
| Customer / phone | `del_customer` + `del_call` |
| Line items | `del_line_*` **below** map/photos (widget assert) |
| Collect | Cash / Mark debt |
| POD → Complete → next | Complete gated on POD; navigates to next open stop |