# idempotency

## Purpose

Replay-safe POST/PUT/PATCH responses via `Idempotency-Key` middleware. Not a domain API — global request middleware.

## Key models

| Model | Role |
|-------|------|
| `IdempotencyRecord` | Cached successful response keyed by user/method/path |

## Public APIs

*(none — global middleware)*

## Bounds & invariants

- Unique on `(key, user, method, path)`; same key + different body → 409.
- Successful responses stored and replayed with `X-Idempotency-Replayed`.
- Failed/4xx responses are generally not replayed as success (see middleware impl).

## Audit

Does not replace domain audit; replays should not double-write side effects.

## Gaps

- Public API docstrings: **done** for ``middleware.py`` and ``IdempotencyRecord``; retention/TTL policy still undocumented in code.
