# agents

## Purpose

Field sales: customer sites/media and field orders that pack into a single sale (no draft stock reservation).

## Key models

| Model | Role |
|-------|------|
| `CustomerSite` / `SiteMedia` | Visit location + media |
| `FieldOrder` / `FieldOrderLine` | Pack → sale; at most one sale per order |

## Public APIs

Prefix: `/api/visits/` (alias `/api/agents/`)

## Bounds & invariants

- Stock allocates on pack only (no draft reservation).
- Pack creates at most one sale (`order.sale` OneToOne; idempotent on `sale_id`).
- Field debt paths must stay aligned with sales FO-debt rules.

## Audit

Pack/assign/create paths emit domain audit (`module=agents` / sales as applicable).

## Gaps

- Google-style docstrings added for models, ``services``, ``order_services``, and ``field_sale``. ViewSet/serializer methods remain thin.
- Domain audit coverage on every pack/assign path — verify against sales/inventory standards.
