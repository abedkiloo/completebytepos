# dispatch

## Purpose

Admin queue over field orders: pack, assign drivers, and driver create. Reuses `agents.FieldOrder` — no separate models.

## Key models

*(none — uses `agents.FieldOrder`)*

## Public APIs

Prefix: `/api/dispatch/`

## Bounds & invariants

- Queue is submitted/packing/ready only.
- Pack/assign require dispatch update perms; no second FO-debt path beside field sale.

## Audit

Dispatch actions should log via audited mixins / `log_domain_event`.

## Gaps

- Audit coverage may still be thinner than inventory/sales — verify on next pass.
- Google-style docstrings on ``views`` (pack/assign actions) and ``driver_create``; list/queue ViewSet methods intentionally brief.
