# Screen inventory — CompleteBytePOS Mobile

Each row: one job, one primary CTA. Personas from `UX_MENTAL_MODELS.md`.

**Hard rule (agent order wizard):** map pin confirmed + ≥1 site photo before submit — screens `AG-SITE-MAP`, `AG-SITE-PHOTO`, `AG-ORDER-REVIEW`.

---

## Auth & shell

| Screen id | Persona | Job | Primary CTA | Sprint |
|-----------|---------|-----|-------------|--------|
| AUTH-SPLASH | all | Cold start only | — (auto advance) | S01 |
| AUTH-LOGIN | all | Sign in | Log in | S02 |
| AUTH-BIOMETRIC | all | Unlock with biometrics (optional) | Unlock | S02 / S11 |
| SHELL-PERSONA | multi-role | Pick active persona | Continue as … | S02 |
| SHELL-SYNC | all | See online/offline + queue depth | View pending | S03 |

---

## Store — Cashier home & POS

| Screen id | Persona | Job | Primary CTA | Sprint |
|-----------|---------|-----|-------------|--------|
| STORE-HOME | cashier | Start selling / resume holding | New sale / Resume holding | S02 |
| POS-CATALOG | cashier | Find products | Add to cart | S04 |
| POS-CART | cashier | Review lines & totals | Checkout | S04 |
| POS-CUSTOMER | cashier | Attach customer | Continue | S04 |
| POS-PAY | cashier | Take payment | Complete sale | S04 |
| POS-RECEIPT | cashier | Confirm success | New sale / Share | S04 |

---

## Store — Customers & debt

| Screen id | Persona | Job | Primary CTA | Sprint |
|-----------|---------|-----|-------------|--------|
| CUST-LIST | cashier / manager | Find customer | Open / Add | S05 |
| CUST-CREATE | cashier / manager | Register walk-in | Save | S05 |
| CUST-DETAIL | cashier / manager | See balance & history | Settle debt | S05 |
| CUST-DEBT-SETTLE | cashier / manager | Reduce what they owe | Confirm payment | S05 |
| CUST-DEBTORS | manager | See who owes | Open debtor | S05 |

---

## Store — Sales history & daily

| Screen id | Persona | Job | Primary CTA | Sprint |
|-----------|---------|-----|-------------|--------|
| SALE-HISTORY | cashier / manager | Find past sales | Open sale | S06 |
| SALE-DETAIL | cashier / manager | Inspect one sale | Refund (if permitted) | S06 |
| SALE-DAILY | manager* | Track paid vs debt by day | Open day / customer | S06 |

\*Requires `sales.daily_sales` — hide nav otherwise.

---

## Store — Manager home extras

| Screen id | Persona | Job | Primary CTA | Sprint |
|-----------|---------|-----|-------------|--------|
| MGR-HOME | manager | What needs attention today | Approvals / Debt / Dispatch | S02 |
| MGR-APPROVALS | manager | Clear pending changes | Approve / Reject | S02+ |
| DISP-QUEUE | dispatcher / manager | Pack & assign field orders | Open order | S08 |
| DISP-ORDER | dispatcher | Pack with site map+photos first | Mark packed / Assign | S08 |

---

## Field agent

| Screen id | Persona | Job | Primary CTA | Sprint |
|-----------|---------|-----|-------------|--------|
| AG-HOME | field agent | Start a visit / order | New visit | S07 |
| AG-SITE-MAP | field agent | Confirm where this place is | **Confirm location** | S07 |
| AG-SITE-PHOTO | field agent | Capture ≥1 recognition photo | **Continue** (disabled until ≥1) | S07 |
| AG-SITE-CUSTOMER | field agent | Who is this visit for | Continue | S07 |
| AG-SITE-REVIEW | field agent | Review pin + photos | Use site / New order | S07 |
| AG-ORDER-CART | field agent | Build field order lines | Review | S08 |
| AG-ORDER-REVIEW | field agent | Confirm site visuals + terms | **Submit to store** | S08 |
| AG-ORDER-LIST | field agent | See my open orders | Open order | S08 |

**Wizard order (mandatory):** `AG-SITE-MAP` → `AG-SITE-PHOTO` → `AG-SITE-CUSTOMER` (horizontal). Cannot skip pin or photo. GPS assists only — user must confirm pin.

---

## Delivery agent

| Screen id | Persona | Job | Primary CTA | Sprint |
|-----------|---------|-----|-------------|--------|
| DEL-HOME | delivery | Complete next stop | Next stop | S09 |
| DEL-ROUTE | delivery | See today’s ordered stops | Open stop | S09 |
| DEL-STOP | delivery | Recognize place → deliver → prove | Arrive / Complete stop | S09 |
| DEL-LINES | delivery (within stop) | Deliver / partial / return qty | Save lines | S09 |
| DEL-COLLECT | delivery (within stop) | Collect cash or mark debt | Confirm collected | S09 / S10 |
| DEL-POD | delivery (within stop) | Capture proof | Complete stop | S09 |
| DEL-STK-WAIT | delivery / cashier | Wait for M-Pesa confirmation | Retry / Query | S10 |

**DEL-STOP layout (mandatory top→bottom):** map + pin → photo carousel + landmark → customer/phone → line items → collect → POD.

---

## Payments & messaging (later)

| Screen id | Persona | Job | Primary CTA | Sprint |
|-----------|---------|-----|-------------|--------|
| PAY-STK-SEND | cashier / delivery | Prompt customer phone | Send M-Pesa prompt | S10 |
| PAY-STK-WAIT | same | Wait for server-confirmed pay | — | S10 |
| MSG-SMS-STATUS | same | Confirm SMS outbox state | Done | S10 |

---

## Coverage check vs requirements

| Flow | Screens | Map+photo rule |
|------|---------|----------------|
| Auth → persona home | AUTH-*, STORE-HOME / AG-HOME / DEL-HOME / MGR-HOME | n/a |
| POS lite | POS-* | n/a |
| Customers & debt | CUST-* | n/a |
| Daily sales | SALE-DAILY | n/a |
| Agent visit → order | AG-SITE-* → AG-ORDER-* | **Enforced** |
| Dispatch | DISP-* | Consume site media |
| Delivery POD | DEL-* | Map+gallery first on DEL-STOP |
| STK + SMS | PAY-* / MSG-* | n/a |
