# suppliers

## Purpose

Supplier master data (types, payment terms, contact) for purchasing reference. Does not mutate stock.

## Key models

| Model | Role |
|-------|------|
| `Supplier` | Vendor master record |

## Public APIs

Prefix: `/api/suppliers/` (CRUD under `/api/suppliers/suppliers/`)

## Bounds & invariants

- Contact/terms are reference data only.
- Stock intake belongs in inventory purchase paths, not here.

## Audit

CRUD via audited ViewSet when enabled.

## Gaps

- Public API docstrings: **done** for ``models.py`` and ``services.py`` (views/serializers still partial).
