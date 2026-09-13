# S07 — Agent sites: mandatory map pin + photo upload

**Paste after `MASTER_PROMPT.md`.**

## Goal

Implement the hard requirement: field agents **must select a location on the map and upload ≥1 site photo** before a site/order can proceed. Delivery agents will consume this data in S09 — design the stop-friendly data model now.

## In scope

### Backend (TDD, ≥98% on new modules)

- `CustomerSite` (or equivalent): customer, label, lat, lng, accuracy, landmark notes, is_default
- `SiteMedia`: site/order FK, image, caption, created_by, created_at
- APIs: create/update site, upload media, list media
- Validation: reject order/site finalize without pin + min media count (config flag)

### Flutter

- Map picker screen: GPS assist → user confirms pin → reverse geocode label if available
- Landmark text field
- Photo capture/gallery multi-upload (min 1), compression, offline outbox for media
- Site review thumbnail
- Agent entry point: “New site visit”
- Config: min photos, max size (from remote config or hardcoded defaults documented)

## Out of scope

- Full field order cart (S08)
- Delivery stop UI (S09) — but **data shape must support map-first stop**
- Turn-by-turn routing

## UX mental model (wizard)

1. **Map** — “Where is this place?” → Confirm location  
2. **Photos** — “How will the driver recognize it?” → Continue  
3. **Customer** — “Who is this for?”  

Horizontal slide between steps. Cannot skip 1–2.

## Tests (TDD)

### Backend

- Cannot create finalized site without lat/lng
- Cannot finalize without ≥1 media
- Permissions for agent role pack (introduce `agents.*` permissions in pack)

### Flutter

- Widget: Confirm disabled until pin set
- Widget: Continue disabled until ≥1 photo
- Unit: compression size bounds
- Unit: outbox media enqueue

## Definition of Done

- [ ] Android: place pin + upload photo + save site against API
- [ ] BE new module coverage ≥98%
- [ ] FE feature coverage ≥98%
- [ ] Agent permission pack documented in role_definitions
- [ ] Delivery-agent “view model” documented (fields stop UI will need)
