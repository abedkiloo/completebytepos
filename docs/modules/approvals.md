# approvals

## Purpose

Store-wide maker-checker: hold sensitive writes as `PendingChange` until a checker applies or rejects. Live entity data stays unchanged while `pending_approval`.

## Key models

| Model | Role |
|-------|------|
| `PendingChange` | Proposed vs original values, apply payload, maker/checker, status |

## Public APIs

Prefix: `/api/approvals/pending-changes/` — list/detail, pending count, my submissions/decisions, approve/reject/resubmit.

Submissions are created via domain `submit_change` integrations (not a public create API).

## Bounds & invariants

- Gated by `StoreSettings.maker_checker_enabled` (plus sales toggles where relevant).
- Maker ≠ checker unless admin override; reason required on submit/reject.
- Price swing >50% needs `extreme_price_confirmed`.
- Stock apply must not go negative when tracked.
- Batch approve/reject applies all pending rows sharing `batch_id`.

## Audit

`log_domain_event` on submit/approve/reject/resubmit (`module=approvals`). Downstream apply owns domain side effects + their audits.

## Gaps

- No separate “approvals module” enable flag.
- List is global (no tenant filter).
