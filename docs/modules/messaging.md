# messaging

## Purpose

SMS templates, outbox, and debt-reminder send/list APIs.

## Key models

| Model | Role |
|-------|------|
| `SmsTemplate` | Reusable message content |
| `MessageOutbox` | Send record of truth |

## Public APIs

Prefix: `/api/messaging/`

## Bounds & invariants

- Sends gated by messaging (or debt_management) permissions.
- Outbox is the send record; templates are content only.

## Audit

Send actions should log who triggered which template/recipients (redact full phone where policy requires).

## Gaps

- Google-style docstrings on models, ``services``, and ``customer_notify`` send helpers.
- ``customer_blast`` / provider modules — doc pass not expanded this wave.
- Bulk send failure leaves outbox rows failed atomically — document ops runbook separately if needed.
