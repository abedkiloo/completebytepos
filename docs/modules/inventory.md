# inventory

## Purpose

Authoritative stock ledger for products/variants: movements, optional FIFO cost layers, and stock checkpoints. Catalog `stock_quantity` is mutated by movement create (and checkpoint deltas). Sales/purchases/adjustments/transfers must go through this app’s services — not raw product updates.

## Key models

| Model | Role |
|-------|------|
| `StockMovement` | Signed qty change; stock side-effect on **create only** |
| `StockLayer` | FIFO intake batch when layers enabled |
| `StockCheckpoint` / `StockCheckpointLine` | Physical count cycle; may block sales |

## Public entry points

- `StockMovementService.adjust_stock` / `purchase_stock` / `transfer_stock` / `undo_transfer`
- `checkpoint_services.open_checkpoint` / `count_*` / `close_checkpoint` / `cancel_checkpoint`
- HTTP: `/api/inventory/` (movements, adjust/purchase/transfer/undo, checkpoints)

## Bounds & invariants

- Adjustment `quantity` must be **non-zero**; positive intake needs `unit_cost > 0` (or reusable positive catalog cost).
- On-hand cannot go negative (row lock + ValidationError) unless sale negative-stock flag applies to sale movements.
- Do not re-save a movement to “fix” qty — create a new movement.
- Transfers are paired OUT/IN; undo reverses both.
- Open checkpoint + `block_sales` blocks POS for pending lines.

## Audit

Every service mutate path logs `stock_*` with `stock_before` / `stock_after`.

## Gaps

- Direct catalog stock edits outside services can desync layers/history.
- Layer vs non-layer cost behavior depends on store feature flags.
