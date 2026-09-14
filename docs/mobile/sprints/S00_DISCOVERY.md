# S00 — Discovery & contracts

**Paste after `MASTER_PROMPT.md`.**

## Goal

Prepare to build without coding the app yet: audit the existing API, lock design tokens, freeze screen inventory, and produce an OpenAPI-oriented contract list for mobile.

## In scope

- Inventory auth, sales, customers, debt, products, inventory endpoints used by web (`fe/src/services/api.js`, `be/*/urls.py`)
- Document permission packs relevant to mobile (cashier, manager, `sales.daily_sales`, future agent packs)
- Screen inventory mapped to personas (see `UX_MENTAL_MODELS.md`)
- Design tokens proposal (colors, type, spacing) consistent with product brand — Android Material 3 friendly
- Decide repo path: `mobile/` vs `apps/mobile/`
- Decide state management (Riverpod **or** Bloc) — write decision in `docs/mobile/DECISIONS.md`
- List backend gaps for S07–S10 (CustomerSite, SiteMedia, FieldOrder, Dispatch, PaymentIntent, MessageOutbox)

## Out of scope

- Flutter UI implementation
- New production features

## Deliverables

1. `docs/mobile/DECISIONS.md` (path, state mgmt, maps provider candidates, local DB candidates)
2. `docs/mobile/API_MOBILE_CONTRACT.md` (endpoint table: method, path, auth, used by which sprint)
3. `docs/mobile/SCREEN_INVENTORY.md` (screen id, persona, job, primary CTA, sprint owner)
4. Updated BACKLOG if needed

## Tests / coverage

- N/A for Flutter this sprint
- If you add any Python helper scripts for auditing, cover them ≥98%

## Definition of Done

- [x] Decisions documented → `docs/mobile/DECISIONS.md` (path `omuwenga/mobile/`, Riverpod, Drift, Google Maps, GoRouter)
- [x] API contract draft reviewed against live `be/` routes → `docs/mobile/API_MOBILE_CONTRACT.md`
- [x] Screen inventory covers store + agent + delivery flows from requirements → `docs/mobile/SCREEN_INVENTORY.md`
- [x] Map-pin + photo hard rule appears in screen inventory for agent order wizard (`AG-SITE-MAP` / `AG-SITE-PHOTO` / `AG-ORDER-REVIEW`)
- [x] Master prompt path confirmed for S01 → paste `MASTER_PROMPT.md` then `sprints/S01_FOUNDATION.md`; `flutter create` in `omuwenga/mobile/`
