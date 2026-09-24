# API mobile contract (draft)

Base prefix: `/api/` · Auth: JWT Bearer (`access`) · Refresh: `POST /api/token/refresh/`  
Source audit: `fe/src/services/api.js` + `be/*/urls.py` + view `@action`s (2026-09-14).

Status legend: **exists** · **gap** (new in later sprint)

---

## Auth & session

| Method | Path | Auth | Notes | Sprint |
|--------|------|------|-------|--------|
| POST | `/accounts/auth/login/` | Public | Returns `access`, `refresh`, `user`, `profile`, `permissions`, `enabled_modules` | S02 |
| POST | `/accounts/auth/logout/` | JWT | Body: `{ refresh }` blacklist | S02 |
| GET | `/accounts/auth/me/` | JWT | Same permission payload as login | S02 |
| POST | `/token/refresh/` | Public | `{ refresh }` → new `access` | S02 |
| POST | `/token/verify/` | Public | Optional client check | S02 |
| GET | `/healthz/` | Public | Smoke / health feature | S01 |

---

## Products & catalog (POS lite)

| Method | Path | Auth / perm | Notes | Sprint |
|--------|------|-------------|-------|--------|
| GET | `/products/` | `products.view` | List / filter | S04 |
| GET | `/products/{id}/` | `products.view` | Detail | S04 |
| GET | `/products/search/?q=&limit=` | `products.view` | POS search | S04 |
| GET | `/products/variants/` | `products.view` | Optional variant lines | S04 |
| GET | `/products/categories/` | `categories.view` | Browse | S04 |
| GET | `/products/units/` | `products.view` | UoM options | S04 |

Out of mobile scope for early sprints: bulk import/export, barcode print admin.

---

## Sales / POS

| Method | Path | Auth / perm | Notes | Sprint |
|--------|------|-------------|-------|--------|
| GET | `/sales/` | `sales.view` | History list + filters | S06 |
| GET | `/sales/{id}/` | `sales.view` | Sale detail | S06 |
| GET | `/sales/{id}/receipt/` | `sales.view` | Receipt payload | S04 / S06 |
| POST | `/sales/` | `sales.create` / POS | Create sale (if used) | S04 |
| GET | `/sales/active-holding/` | `sales` / POS | Resume holding | S04 |
| POST | `/sales/holding/` | `sales.create` | Save holding | S04 |
| POST | `/sales/{id}/checkout/` | `sales.create` | Complete sale | S04 |
| POST | `/sales/{id}/cancel-holding/` | `sales.update` | Cancel holding | S04 |
| POST | `/sales/{id}/refund/` | `sales.refund` | Manager; hide if no perm | S06+ |
| GET | `/sales/dashboard-summary/` | `sales.view` | Optional manager home | S02 home |
| GET | `/sales/daily/` | **`sales.daily_sales`** | Daily tracker | S06 |
| GET | `/sales/daily/customer/{customerId}/` | **`sales.daily_sales`** | Customer day drill | S06 |

---

## Customers & debt

| Method | Path | Auth / perm | Notes | Sprint |
|--------|------|-------------|-------|--------|
| GET | `/sales/customers/` | `customers.view` | Search / list | S05 |
| GET | `/sales/customers/{id}/` | `customers.view` | Basic | S05 |
| GET | `/sales/customers/{id}/detail/` | `customers.view` | Rich detail | S05 |
| POST | `/sales/customers/` | `customers.create` | Create | S05 |
| PUT | `/sales/customers/{id}/` | `customers.update` | Update | S05 |
| GET | `/sales/customers/{id}/wallet-transactions/` | `customers.view` | Wallet ledger | S05 |
| POST | `/sales/customers/{id}/receive-wallet-payment/` | `customers.update` | Settle debt | S05 |
| GET | `/sales/customers/debt-summary/` | `customers.view` | Debt KPIs | S05 |
| GET | `/sales/customers/debtors/` | `customers.view` | Debtors list | S05 |
| GET | `/sales/customers/debtor-count/` | `customers.view` | Badge count | S05 |

---

## Inventory (read-lite)

| Method | Path | Auth / perm | Notes | Sprint |
|--------|------|-------------|-------|--------|
| GET | `/inventory/low_stock/` | `inventory.view` | Manager alerts optional | S02+ |
| GET | `/inventory/` | `inventory.view` | Movements — not primary mobile | backlog |

Write paths (adjust/purchase/transfer) stay web-first unless a later sprint pulls them in.

---

## Approvals (manager optional)

| Method | Path | Auth | Notes | Sprint |
|--------|------|------|-------|--------|
| GET | `/approvals/pending-changes/pending/` | JWT + approve perms | Manager home secondary | S02+ |

---

## Backend gaps (S07–S10) — historical; S07–S10 now exist

### S07 — Sites & media

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET/POST | `/agents/sites/` | `agents.*` | `CustomerSite`: customer, label, lat, lng, accuracy, landmark, is_default, status |
| GET/PATCH | `/agents/sites/{id}/` | `agents.*` | Draft updates; cannot clear pin once finalized |
| POST | `/agents/sites/{id}/finalize/` | `agents.update` | Requires pin + ≥1 media + customer |
| GET/POST | `/agents/sites/{id}/media/` | `agents.*` | `SiteMedia` multipart |
| DELETE | `/agents/sites/{id}/media/{mediaId}/` | `agents.update` | Blocks removing last photo when finalized |
| GET | `/agents/sites/config/` | `agents.view` | `min_site_media`, `max_site_media`, `max_site_image_bytes` |

**Hard rule:** reject finalize without confirmed pin + ≥1 photo (+ customer).

### S08 — Field orders & dispatch

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET/POST | `/agents/field-orders/` | `agents.*` | Lines + `site_id`; status machine |
| POST | `/agents/field-orders/{id}/submit/` | `agents.*` | Requires site pin + media + customer + lines |
| GET | `/dispatch/queue/` | `dispatch.*` | Submitted / packing / ready |
| POST | `/dispatch/field-orders/{id}/pack/` | `dispatch.*` | Stock allocate-on-pack (`stock_allocated`) |
| POST | `/dispatch/field-orders/{id}/assign/` | `dispatch.*` | `{ delivery_agent_id }` |

Statuses: `draft → submitted → packing → ready → out_for_delivery → done|cancelled`  
**Status:** exists (S08).

### S09 — Delivery & POD

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | `/delivery/routes/today/` | `delivery.view` | Ordered stops; syncs assigned OFD orders |
| GET | `/delivery/routes/today/geometry/` | `delivery.view` | Cached depot + numbered pins + polyline (own route) |
| GET | `/delivery/routes/geometry/` | Authenticated; own route or `dispatch.view` / manager | `?agent_id=&date=` staff map. Past dates need `delivery.history` |
| GET | `/delivery/routes/lookup/` | Same as geometry | Stops for that agent+date; does not create today |
| GET | `/delivery/routes/` | Authenticated | List routes. Past range needs `delivery.history` |
| GET | `/delivery/routes/{id}/` | Same as lookup | Full route + stops |
| GET | `/delivery/config/` | `delivery.view` | `require_pod_to_complete`, `allow_offline_pod_queue`, `maps` (`can_view_history`) |
| GET | `/delivery/stops/{id}/` | `delivery.view` | Map + media + lines first in payload |
| POST | `/delivery/stops/{id}/arrive/` | `delivery.update` | Status transition |
| POST | `/delivery/stops/{id}/start/` | `delivery.update` | pending→arrived→delivering |
| POST | `/delivery/stops/{id}/lines/` | `delivery.update` | Delivered / returned qty (partial validation) |
| POST | `/delivery/stops/{id}/collect/` | `delivery.update` | Cash / debt / defer_stk |
| POST | `/delivery/stops/{id}/pod/` | `delivery.update` | Signature + photo + lat/lng (multipart or b64) |
| POST | `/delivery/stops/{id}/complete/` | `delivery.update` | Requires POD when configured |
| POST | `/delivery/stops/{id}/propose-pin/` | `delivery.update` | Optional corrected pin (pending approval) |

Stop statuses: `pending → arrived → delivering → collected → completed|failed`  
**Status:** exists (S09).

### S10 — Payments & SMS

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | `/payments/intents/` | `payments.create` | `PaymentIntent` create |
| POST | `/payments/intents/{id}/stk/` | `payments.create` | Server-side Daraja only |
| GET | `/payments/intents/{id}/` | `payments.view` | Poll status — never trust client |
| POST | `/payments/intents/{id}/query/` | `payments.create` | STK query reconciler |
| POST | `/payments/daraja/callback/` | Public | Idempotent callback |
| GET | `/public/invoices/{token}/` | Public | Tokenized invoice payload |
| POST | `/messaging/reminders/debt/` | `messaging.create` | Overdue wallet debt SMS |

Statuses: `created → prompted → paid|failed|cancelled|expired`  
**Status:** exists (S10).

---

## Idempotency & offline (cross-cutting)

| Concern | Contract expectation | Sprint |
|---------|----------------------|--------|
| Writes | Client sends `Idempotency-Key` (UUID) header on POST/PUT/PATCH | S03+ |
| Server | `IdempotencyMiddleware` replays prior response; body mismatch → 409 | S03 |
| Offline creates | Client-generated UUID as resource id where API allows | S03 |
| Media upload | Compress client-side; queue via outbox when offline | S07 |
| Fake success | Forbidden — show pending queue depth | S03 |

### Offline-safe vs online-only (mobile)

| Class | Endpoints | Notes |
|-------|-----------|-------|
| **Offline-safe writes** (outbox + Idempotency-Key) | `POST /sales/`, `POST /sales/holding/`, `POST /sales/{id}/checkout/`, `POST /sales/customers/`, `PUT /sales/customers/{id}/`, `POST .../receive-wallet-payment/` | Wire in S04–S05 using sync core |
| **Offline-safe reads** (cache) | `GET /products/**` catalog | CachedProducts table (S03 placeholder → S04) |
| **Online-only** | Auth login/refresh/logout, Daraja STK, live stock allocate-on-pack, approvals that need immediate manager presence | Do not enqueue; show offline banner |
| **Later outbox** | Site media uploads, POD photos | S07 / S09 extend outbox |

---

## OpenAPI note

No checked-in OpenAPI spec today. This table is the mobile contract source until an export is generated from DRF (optional backlog). Prefer regenerating from live routes when adding gap endpoints.
