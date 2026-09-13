# UX mental models — CompleteBytePOS Mobile

Use this when designing or reviewing screens. Each screen answers:

1. **Who am I?** (persona)
2. **What is my job on this screen?** (one job)
3. **What is the one next action?** (primary CTA)
4. **How do I go back / cancel safely?**

---

## Global navigation psychology

| Pattern | When | Feeling |
|---------|------|---------|
| Bottom nav (3–5 items) | Store cashier / manager home | Stable “home base” |
| Persona switcher (if multi-role user) | Rare | Explicit role change, not buried |
| Stack push | Drill into detail | Forward progress |
| Modal / sheet | Confirm, filters, quick pay | Temporary, dismissible |
| Full-screen wizard | New order, new site, POD | Steps with progress dots |
| Horizontal page slide | Wizard steps | “I’m advancing a process” |

**Rule:** Never use a wizard for a single field. Never use a modal for a multi-step process.

---

## Persona homes (first screen after login)

### Cashier
- **Job:** Start selling or resume holding.
- **Primary CTA:** Open POS / New sale.
- Secondary: Customers, History.
- Avoid: reports clutter, settings.

### Manager
- **Job:** See what needs attention today.
- **Primary:** Approvals / Open debt / Dispatch queue (when built).
- Secondary: Daily sales (if `sales.daily_sales`), stock alerts.

### Field agent
- **Job:** Visit → pin site → order.
- **Primary:** New visit / New order.
- Secondary: My open orders, Today’s stops (if delivery role).

### Delivery agent
- **Job:** Complete the next stop.
- **Primary:** Next stop (map-first).
- Secondary: Route list, cash collected today.

---

## Critical flows — screen-by-screen

### A. Auth
- Login → (optional biometric unlock) → Persona home.
- Errors: inline, not toast-only. Lockout messaging clear.

### B. POS lite
1. Catalog/search (scanner icon always visible)
2. Cart sheet / cart screen (totals sticky)
3. Customer attach (optional/required per module flags)
4. Pay (method + amount) → success receipt
- Back from cart: confirm if non-empty.

### C. Customer debt settle
- Identity band → owed amount hero → amount + method → confirm → success.
- Mental model: “I’m reducing what they owe,” not “generic payment form.”

### D. Agent site capture (MANDATORY)
1. Map full-bleed → drag/tap pin → **Confirm location** (primary)
2. Landmark note (optional but encouraged)
3. Camera/gallery → ≥1 photo → **Continue**
4. Customer select/create
- Cannot skip pin or photo. GPS is assist only.
- Transition: horizontal wizard (map → photos → customer).

### E. Field order submit
- Cart → review site thumbnail+pin → terms → Submit to store.
- Success: “Store will pack — you’ll be notified.”

### F. Delivery stop (MAP FIRST)
1. **Map** (pin) + Open in Maps
2. **Photo carousel** + landmark
3. Customer / phone
4. Line items (deliver / partial / return)
5. Collect money
6. POD signature/photo → Complete stop → auto-advance next
- Psychology: recognition of place before inventory work.

### G. STK payment (later)
- Waiting state with clear “prompt sent to 07…” 
- Success only after server confirms — never on “I think they paid.”

---

## Motion checklist

- List → detail: shared-axis slide
- Wizard steps: horizontal shared-axis
- Paywall / destructive: fade + scale sheet
- Sync status: subtle persistent chip (not modal)
- Prefer 200–320ms; respect reduced-motion if available

---

## Accessibility & field conditions

- Large tap targets (≥48dp)
- High contrast outdoors
- Works with one dirty hand (big CTAs)
- Offline banner always visible when disconnected
