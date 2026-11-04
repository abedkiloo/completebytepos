# delivery

## Purpose

Delivery routes/stops, proof of delivery (POD), and proposed pin corrections for out-for-delivery work.

## Key models

| Model | Role |
|-------|------|
| `DeliveryRoute` / `DeliveryStop` | Today's assignee workload |
| `DeliveryLineResult` | Per-line outcome |
| `ProofOfDelivery` | Completion evidence |
| `ProposedPinCorrection` | Proposed site coord fix (not silent overwrite) |

## Public APIs

Prefix: `/api/delivery/`

## Bounds & invariants

- Stops/routes drive assignee workload; POD records completion evidence.
- Pin corrections are proposed, not silent overwrites of site coords.

## Audit

POD and status transitions should emit audit rows.

## Gaps

- Google-style docstrings on models, ``services``, and ``assignees`` (POD/route/collect paths documented).
- Audit rows on all stop/POD mutations and delivery ViewSet edges — still verify.
- ``DeliveryLineResult.stock_applied`` is a stub until inventory return ledger hooks exist.
