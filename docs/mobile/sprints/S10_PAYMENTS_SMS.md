# S10 — M-Pesa STK payments + SMS receipts/reminders

**Paste after `MASTER_PROMPT.md`.**

## Goal

Agents/cashiers can request an M-Pesa STK prompt; system records PaymentIntent; on confirmed pay, send branded SMS with invoice link (Misspat-style template variables). Reminders for debt.

## In scope

### Backend (secrets server-side only)

- `PaymentIntent` state machine: created → prompted → paid/failed/cancelled/expired
- Daraja STK initiate + callback + STK query reconciler
- Idempotent callback handling
- `MessageOutbox` + SMS provider adapter
- Public tokenized invoice URL page (or API the link resolves to)
- SMS template with variables: customer name, brand blurb, invoice no, amount, link
- Reminder job/API for overdue wallet debt (basic)

### Flutter

- “Send M-Pesa prompt” on collect screens (POS, debt settle, delivery stop)
- Waiting UI until server says paid/failed (poll or websocket/push)
- Never mark paid from client guesswork
- Show SMS sent confirmation state

## Out of scope

- Airtel pay-link (BACKLOG)
- Full marketing campaign tool

## UX mental model

- “We asked their phone to pay → we wait together → money is real only when confirmed”
- Waiting state calm; timeout with retry/query

## Security

- No secrets on device
- Callback verification / correlation IDs
- OTP-on-SMS optional enhancement (BACKLOG if not this sprint)

## Tests (TDD)

- BE: intent idempotency, callback duplicate, query reconcile
- BE: SMS rendered template snapshot
- FE: waiting/success/fail widgets
- Coverage ≥98% on payments + messaging modules

## Definition of Done

- [x] Sandbox STK success path tested (FakeDaraja + FE wait/query)
- [x] SMS template matches agreed copy structure
- [x] Android collect flow uses intents (POS / debt settle / delivery Request M-Pesa)
- [x] Coverage gates green (BE payments+messaging 100%; FE `lib/features/payments` 100%)

## Android smoke notes

1. Online only: offline shows “M-Pesa STK requires a connection”.
2. POS → M-Pesa → enter phone → Send prompt → wait → Done only after server `paid`.
3. Debt settle with customer phone → same wait UI → wallet receive uses receipt ref.
4. Delivery stop → Request M-Pesa → amount dialog → wait → `collect` with `defer_stk` + receipt notes.
5. Paid + `sms_sent` shows “SMS sent” confirmation.
