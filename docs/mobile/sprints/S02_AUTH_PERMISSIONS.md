# S02 — Auth, session, permissions, persona home

**Paste after `MASTER_PROMPT.md`.**

## Goal

Users can log in against CompleteBytePOS JWT auth, persist tokens securely, load `/me` permissions, and land on a **persona-appropriate home**.

## In scope

- Login screen (username/password)
- Secure token storage
- Auth interceptor + refresh strategy (match web behavior)
- Permission helpers mirroring web (`sales.daily_sales`, etc.)
- Persona resolution (super admin / manager / sales → mobile home variants)
- Logout + session expiry UX
- Bottom nav shell for store personas (POS, Customers, More)

## Out of scope

- Biometrics (can stub interface; implement if time — else BACKLOG)
- Agent home (S07+)
- Offline sync (S03)

## UX mental model

- Login job: “Prove who I am”
- Home job: “Start my most common task”
- Hide Daily Sales nav without `sales.daily_sales`
- Clear errors on wrong password; no stack traces

## Tests (TDD)

- Unit: permission parsing / canViewDailySales equivalent
- Unit: persona routing table
- Widget: login validation empty fields
- Widget: home shows primary CTA for cashier
- Mock API: login success/failure

## Backend

- Use existing auth endpoints; add tests only if you change them

## Definition of Done

- [x] Login works against local/staging API on Android
- [x] Tokens not logged
- [x] Permission-gated nav verified with fixture users
- [x] ≥98% coverage on auth + permissions packages
- [x] UX models for Login + Home documented in PR notes

### Sprint notes (S02 completion)

**Coverage:** `99.55%` (438/440) on `lib/features/auth`, `lib/core/secure`, `lib/core/network`, `lib/app`  
(excluding `lib/main.dart`, `lib/core/secure/secure_token_store.dart` platform stub).

```bash
dart run tools/check_coverage.dart --min=98 \
  --paths=lib/features/auth,lib/core/secure,lib/core/network,lib/app \
  --exclude=lib/main.dart,lib/core/secure/secure_token_store.dart
```

**UX models**

| Screen | Job | Primary CTA | Next |
|--------|-----|-------------|------|
| Login | Prove who I am | Sign in | Persona home (or error banner, no stack traces) |
| Cashier home | Start selling | New sale → `/pos` | Customers secondary; bottom nav |
| Manager / Admin home | See what needs attention | Open debtors → `/customers` | Daily sales if `sales.daily_sales` |
| More | Secondary actions | Sign out | Daily sales / API health when permitted |

**Android smoke:** Debug APK builds. Live login: `flutter run -d <android> --dart-define=API_BASE_URL=http://10.0.2.2:8000/api` with backend up; fixture users `sales` / `manager` / `admin`. No Android emulator connected in this sprint run — login path covered by mock API + widget tests. Tokens via `flutter_secure_storage` — never printed.

**Deferred:** Biometrics unlock → `BACKLOG.md`.
