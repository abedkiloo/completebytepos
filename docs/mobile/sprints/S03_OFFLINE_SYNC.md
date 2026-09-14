# S03 — Offline-first sync core

**Paste after `MASTER_PROMPT.md`.**

## Goal

Install the offline foundation: local database, outbox queue, client UUIDs, connectivity indicator, and sync status UI. Later features depend on this.

## In scope

- Local DB selection implemented (per S00 decision)
- Encrypted storage for PII caches where applicable
- Outbox: enqueue mutation → retry with backoff → mark synced/failed
- Idempotency keys on mutating requests
- Sync status chip (online/offline + pending count)
- Conflict/failure surface (retry/discard) minimal UI
- Catalog cache placeholder table (products) for later POS offline read

## Out of scope

- Full offline POS checkout (wire in S04 using this core)
- Photo upload queue (S07 will extend outbox for media)

## UX mental model

- Chip is ambient trust: “My work is saved / waiting”
- Failed sync items must be human-readable, not JSON dumps

## Tests (TDD)

- Unit: enqueue / dequeue / retry / permanent fail
- Unit: client UUID uniqueness
- Unit: idempotency key stable across retries
- Widget: status chip states (online, offline, pending>0, error)

## Backend

- Document which endpoints are offline-safe vs online-only
- Add server idempotency support if missing for chosen write endpoints (TDD in Django ≥98% on new code)

## Definition of Done

- [x] Sync package ≥98% coverage
- [x] Demo: airplane mode enqueue → reconnect drains queue (instrumented test or manual + unit proof)
- [x] No silent data loss paths without failing tests

### Sprint notes (S03 completion)

**Flutter coverage:** ≥98% on `lib/sync` + `lib/core/network`  
(excluding generated Drift, table defs, `ConnectivityPlusMonitor`, `SecurePiiKeyStore`, `AppDatabase` file opener).

```bash
dart run tools/check_coverage.dart --min=98 \
  --paths=lib/sync,lib/core/network \
  --exclude=lib/sync/data/app_database.g.dart,lib/sync/data/tables.dart,lib/sync/data/app_database.dart,lib/sync/application/connectivity_plus_monitor.dart,lib/sync/data/secure_pii_key_store.dart
```

**Demo proof:** `test/sync/application/sync_engine_test.dart` — offline enqueue stays pending; reconnect drain marks synced; permanent HTTP failures never silently drop.

**Backend:** `be/idempotency/` middleware + model; document offline-safe matrix in `API_MOBILE_CONTRACT.md`.

**Encryption:** AES field-level via `AesPiiCipher` + key in secure storage (prod override); product `encryptedPayload` column ready for PII attributes.
