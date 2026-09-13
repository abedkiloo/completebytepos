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

- [ ] Login works against local/staging API on Android
- [ ] Tokens not logged
- [ ] Permission-gated nav verified with fixture users
- [ ] ≥98% coverage on auth + permissions packages
- [ ] UX models for Login + Home documented in PR notes
