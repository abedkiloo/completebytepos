# Performance & scale readiness

Senior capacity review target: **~40 000 concurrent sessions / ~40 000 requests per minute**. CompleteBytePOS as shipped on a small single-node VPS is **not** at that class yet. This document records the verdict, what we changed in-app **without Redis**, and the later infra path.

## Current stance: no Redis (for now)

- Default cache is **LocMem** (`config/cache.py`). Do **not** set `REDIS_URL`.
- Prefer **`GUNICORN_WORKERS=1`** and **`GUNICORN_THREADS=8`** so LocMem cache, report short-TTL, and throttle counters live in one process.
- Raising workers without Redis splits LocMem (weaker throttles / duplicate cache work). Defer that until Redis is introduced later.

## Verdict (honest)

| Target | Fit today |
|--------|-----------|
| ~40k concurrent TCP connections | No — needs horizontal edge + pooler + (later) shared cache |
| ~40k req/min (~667 RPS) | No on a small single node |
| Tens of concurrent cashiers on one tuned node | Plausible with LocMem + 1×8 Gunicorn |

## What we hardened without Redis

1. **LocMem cache** for SettingsService + short report TTL (per process).
2. **Report + heavy-read throttles** (`reports` 120/min, `heavy_read` 60/min). **Sale checkout stays unthrottled.** Login / SMS rates unchanged.
3. **Product-trends short TTL** (`REPORT_CACHE_SECONDS`, default 20s) — LocMem; still cuts repeat work on the same worker.
4. **List page-size cap** (`API_MAX_PAGE_SIZE`, default 200); FE catalog/pickers aligned to 200.
5. **Call-book** thinner columns + streamed week calls (`iterator`) — less RAM, same business rules.
6. **Gunicorn LocMem-friendly defaults** — 1 worker × 8 threads in compose / `.env.example`.

## Later (when you enable Redis)

1. `pip install redis`, set `REDIS_URL`, optionally raise `GUNICORN_WORKERS`.
2. PgBouncer + `DB_CONN_MAX_AGE=0` behind it.
3. Horizontal replicas; async export/SMS workers; nginx-only `/media`.

## Security non-negotiables

- Do not disable login throttle, JWT blacklist rotation, idempotency, or report permission gates.
- Never remove throttles on public/login surfaces to “go faster”.

## Related knobs (`.env.example`)

`CACHE_TIMEOUT`, `REPORT_CACHE_SECONDS`, `API_MAX_PAGE_SIZE`, `THROTTLE_REPORTS_RATE`, `THROTTLE_HEAVY_READ_RATE`, `GUNICORN_*`, `DB_CONN_MAX_AGE`, `POSTGRES_MAX_CONNECTIONS`.  
(`REDIS_URL` intentionally unset until Redis is adopted.)
