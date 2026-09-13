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

- [ ] Sandbox STK success path tested
- [ ] SMS template matches agreed copy structure
- [ ] Android collect flow uses intents
- [ ] Coverage gates green
