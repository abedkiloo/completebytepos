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

- [ ] Sync package ≥98% coverage
- [ ] Demo: airplane mode enqueue → reconnect drains queue (instrumented test or manual + unit proof)
- [ ] No silent data loss paths without failing tests
