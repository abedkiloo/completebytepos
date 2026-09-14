# Mobile technical decisions

Filled in during **S00** (2026-09-14). Do not change casually after S01 starts.

| Decision | Choice | Rationale | Date |
|----------|--------|-----------|------|
| Repo path | `omuwenga/mobile/` (sibling of `CompleteBytePOS/`) | User-created app root; keeps Flutter outside Django tree; docs stay in `CompleteBytePOS/docs/mobile/` | 2026-09-14 |
| State management | **Riverpod** | Predictable DI + testability; avoid Bloc mix; codegen optional later | 2026-09-14 |
| Local DB | **Drift** (S03) | Typed SQL, migrations, good for outbox/sync; field-level AES for PII blobs | 2026-09-14 |
| Outbox | Drift `OutboxItems` + `SyncEngine` | Enqueue → backoff retry → synced/failed; never fake success | 2026-09-14 |
| Idempotency | Client `Idempotency-Key` + `be/idempotency` middleware | Stable key across retries; replay / 409 on body mismatch | 2026-09-14 |
| Maps SDK | **Google Maps** (S07) | Android-first Play Services; Mapbox remains fallback if billing/keys force switch | 2026-09-14 |
| Navigation | **GoRouter** | Typed routes, redirects for auth, matches S01 prompt | 2026-09-14 |
| Token storage | **flutter_secure_storage** (+ `InMemoryTokenStore` for tests) | JWT access/refresh; never log tokens | 2026-09-14 |
| Auth refresh | Single-flight refresh on 401 (match web SPA) | `ApiClient` + `AuthSessionExpiredException` → login | 2026-09-14 |
| Stock on field order | **Allocate on pack** | Field drafts may cancel; reserve only when dispatcher packs (S08) | 2026-09-14 |
| Offline POD queue | **Allowed** (`ALLOW_OFFLINE_POD_QUEUE`) | Capture signature/photo/pin offline → outbox; never fake complete until server accepts (S09) | 2026-09-14 |
| SMS provider | **FakeSmsProvider** (tests/dev) + **Africa’s Talking** adapter | Adapter behind `MessageOutbox`; AT for sandbox/prod when keys set; Twilio remains BACKLOG | 2026-09-14 |
| Daraja env | Sandbox first (`FakeDaraja` in tests) | S10; secrets stay on server | 2026-09-14 |

---

## Design tokens (proposal — Material 3 friendly)

Aligned with web SPA tokens in `fe/src/index.css` (retail green primary). Flutter ThemeData / ColorScheme mapping for S01.

| Token | Web (HSL) | Flutter approx (ARGB) | Use |
|-------|-----------|----------------------|-----|
| `background` | `0 0% 100%` | `#FFFFFFFF` | Scaffold |
| `foreground` | `222 47% 11%` | `#FF0F172A` | Body text |
| `primary` | `142 71% 40%` | `#FF1E9E4B` | Primary CTA |
| `primaryForeground` | `0 0% 100%` | `#FFFFFFFF` | On primary |
| `secondary` / `muted` | `220 14% 96%` | `#FFF1F5F9` | Surfaces, chips |
| `mutedForeground` | `220 9% 46%` | `#FF64748B` | Secondary text |
| `destructive` | `0 84% 60%` | `#FFEF4444` | Void / refund |
| `success` | `142 71% 45%` | `#FF22C55E` | Paid / in stock |
| `warning` | `38 92% 50%` | `#FFF59E0B` | Low stock / pending |
| `border` / `input` | `220 13% 91%` | `#FFE2E8F0` | Dividers, fields |
| `radius` | `0.5rem` | `8.0` | Default corner |

**Typography (expressive, not Inter/Roboto defaults):**

| Role | Family candidate | Size / weight |
|------|------------------|---------------|
| Display / brand | `Plus Jakarta Sans` or `DM Sans` | 28–32 / w700 |
| Title | same | 20–22 / w600 |
| Body | same | 16 / w400 |
| Label / CTA | same | 14–16 / w600 |
| Mono (receipt #) | `JetBrains Mono` or `Roboto Mono` | 13 / w500 |

**Spacing scale (dp):** 4 · 8 · 12 · 16 · 24 · 32 · 48  
**Touch:** min 48dp primary targets (web POS uses 44px; mobile goes 48).  
**Motion:** 200–320ms; shared-axis list→detail; horizontal wizards; fade sheets.

---

## Permission packs relevant to mobile

| Persona | Existing role / pack | Key permissions for nav |
|---------|----------------------|-------------------------|
| Cashier / Sales | `Sales Personnel` | `pos.view/create`, `sales.view/create`, `customers.view/create/update`, `products.view`, `invoicing.view/create` |
| Manager | `Manager` | Above + `inventory.*` (no delete), `reports.view`, finance view/create; **not** default `sales.daily_sales` |
| Daily sales viewer | Grant `sales.daily_sales` | Daily tracker screens (S06) — admin-grantable, not in default manager pack |
| Field agent | **Field Agent** (`ROLE_FIELD_AGENT`) | `agents.view/create/update` + `customers.view/create/update` + `products.view` — sites, media, field orders (S07–S08) |
| Dispatcher | **Dispatcher** (`ROLE_DISPATCHER`) | `dispatch.view/update` — queue, pack (allocate-on-pack), assign delivery agent (S08) |
| Delivery agent | **Delivery Agent** (`ROLE_DELIVERY_AGENT`) | `delivery.view/update` — today’s route, arrive/deliver/collect/POD/complete (S09) |

Auth payload already returns `permissions[]` + `enabled_modules` from `POST /api/accounts/auth/login/` and `GET /api/accounts/auth/me/` — mobile must gate nav from that list (RBAC parity).

---

## Candidate notes (not locked until sprint)

| Area | Candidates | Locked in |
|------|------------|-----------|
| Local DB | Drift ✅ / Isar / Hive | S03 |
| Maps | Google Maps ✅ / Mapbox | S07 |
| SMS | Africa's Talking ✅ (+ FakeSmsProvider) / Twilio BACKLOG | S10 |

---

## Master prompt path for S01

1. Paste [`MASTER_PROMPT.md`](./MASTER_PROMPT.md)  
2. Paste [`sprints/S01_FOUNDATION.md`](./sprints/S01_FOUNDATION.md)  
3. Create Flutter project at **`omuwenga/mobile/`** (this decision — do not use `apps/mobile/`)
