# CompleteBytePOS Mobile (Flutter) — Sprint Build System

**Platform:** Flutter (Android first; iOS-ready architecture)  
**Backend:** Existing CompleteBytePOS Django/DRF API  
**Method:** TDD · ≥98% coverage per sprint · UX mental-model screens  
**Source of truth:** Requirements map in Cursor canvas `mobile-app-requirements-map` + this folder  

---

## How to use these prompts

Fastest path: follow [`COPY_PASTE_STARTER.md`](./COPY_PASTE_STARTER.md).

1. Open a **fresh agent chat** (or Composer) for **one sprint only**.
2. Paste **`MASTER_PROMPT.md`** first (global laws).
3. Paste that sprint’s file from `sprints/` (e.g. `S01_FOUNDATION.md`).
4. Do **not** start the next sprint until the Definition of Done checklist in the sprint file is fully green.
5. Keep Android as the primary run target (`flutter run` / device / emulator). Do not block on iOS signing in early sprints.

---

## Sprint roadmap (12 sprints)

| Sprint | Name | Primary outcome |
|--------|------|-----------------|
| S00 | Discovery & contracts | API audit, OpenAPI notes, screen inventory, design tokens |
| S01 | App foundation | Flutter app shell, DI, routing, theme, TDD harness, coverage gate |
| S02 | Auth & permissions | Login, secure storage, persona home, RBAC parity with web |
| S03 | Offline sync core | Local DB, outbox, client UUIDs, sync status UI |
| S04 | Store POS lite | Product search, cart, checkout, receipt view |
| S05 | Customers & debt | Customer CRUD lite, wallet debt, settle payment |
| S06 | Sales history & daily sales | History, filters, daily tracker (permission-gated) |
| S07 | Agent sites: map + upload | Mandatory map pin + site photos; CustomerSite/SiteMedia |
| S08 | Field orders & dispatch | Agent order → store pack → assign delivery |
| S09 | Delivery run & POD | Stop-first UI (map/gallery), line deliver/return, signature |
| S10 | Payments STK + SMS | PaymentIntent, Daraja STK, SMS templates, public invoice link |
| S11 | Polish, MDM lite, release | Performance, device trust, Android release, coverage audit |

---

## Non-negotiable Definition of Done (every sprint)

- [ ] **TDD:** tests written/updated **before** or with implementation; failing test first for new behavior
- [ ] **Coverage:** `flutter test --coverage` then lcov report shows **≥98% lines** for packages/files touched this sprint (see Master Prompt for scope rules)
- [ ] **Android:** builds and runs on Android emulator or device
- [ ] **UX:** every new screen has a documented mental model (goal → primary action → next)
- [ ] **Permissions:** UI and API calls respect role packs; no secret/config keys on device
- [ ] **No scope bleed:** only this sprint’s backlog; file follow-ups in `docs/mobile/BACKLOG.md`

---

## Related files

- [`COPY_PASTE_STARTER.md`](./COPY_PASTE_STARTER.md) — exact paste order + calendar  
- [`MASTER_PROMPT.md`](./MASTER_PROMPT.md) — paste this every sprint  
- [`sprints/`](./sprints/) — one prompt per sprint  
- [`UX_MENTAL_MODELS.md`](./UX_MENTAL_MODELS.md) — screen psychology & motion  
- [`COVERAGE_POLICY.md`](./COVERAGE_POLICY.md) — how 98% is measured  
- [`DECISIONS.md`](./DECISIONS.md) — S00 decisions (path, Riverpod, Drift, maps, tokens)  
- [`API_MOBILE_CONTRACT.md`](./API_MOBILE_CONTRACT.md) — endpoint table + S07–S10 gaps  
- [`SCREEN_INVENTORY.md`](./SCREEN_INVENTORY.md) — screens by persona + sprint  
- [`BACKLOG.md`](./BACKLOG.md) — deferred items  
- Flutter app root: `omuwenga/mobile/` (sibling of `CompleteBytePOS/`)  
- Canvas: `flutter-sprint-build-pack` — sprint roadmap overview
