# payments

## Purpose

M-Pesa STK payment intents (POS/debt/delivery) plus Daraja callback handling and public invoice token access.

## Key models

| Model | Role |
|-------|------|
| `PaymentIntent` | Intent lifecycle; unique `public_token` / optional `client_uuid` |

## Public APIs

Prefix: `/api/payments/` (+ public `/api/public/invoices/<token>/`)

## Bounds & invariants

- Callback processed once (`callback_processed`).
- Status machine: created → prompted → paid/failed/cancelled/expired.
- Same client UUID must not create duplicate live intents (idempotent create).

## Audit

Intent create/callback success paths should be auditable without logging secrets/tokens in cleartext.

## Gaps

- Google-style docstrings on ``PaymentIntent`` and ``services`` (create/STK/callback/SMS).
- View/serializer layers not fully documented; never log ``public_token`` or Daraja secrets in audit/examples.
- Expired/cancelled intent transitions — confirm product rules vs code paths.
