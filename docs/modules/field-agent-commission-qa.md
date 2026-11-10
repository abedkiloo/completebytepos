# Field sales commission — QA test script

**How to use:** Work top to bottom. For each case: do the steps → check Expected → mark Pass/Fail.  
**Default under test:** Daily band awards from the Omuwenga Sales Agent Commission Structure (editable in Payroll → Settings).  
**Field sales only:** shop POS sales must not count.  
**Credit to:** `served_by` if set, else `cashier`.  
**Same-day full pay required** for a sale to qualify. By default, product names matching configurable keywords (starter: zip, sofa cup holder) do **not** count toward qualifying sales — they still appear on POS and agent sales views.

---

## 0. One-time setup (do before any case)

| Step | Action |
|------|--------|
| 0.1 | Log in as **Admin / Super Admin**. |
| 0.2 | Confirm **Payroll** module is on. |
| 0.3 | Confirm module feature **Payroll → Sales commission** is **on**. |
| 0.4 | Open **Payroll → Settings**. Tick **Include sales-agent commission**. |
| 0.5 | Confirm **Sales agent award template** shows the PDF default bands (0 / 500 / 1000 / 2000 / 3500 / 4000) and transport 5,000 → 200. |
| 0.6 | Create (or pick) **Agent A** — Field Sales, linked Employee. |
| 0.7 | Keep a clean day **D** (today or a known test day) with no other field sales for A. |

**Pass setup when:** Template bands match the PDF starter; Agent A exists; setting is on.

---

## Positive scenarios

### POS-01 — Dashboard shows today’s band (zero sales)

| Step | Action |
|------|--------|
| 1 | Log in as Agent A (web or app). |
| 2 | Open home / dashboard. |

**Expected**
- **Daily commission** card visible.
- Qualifying sales **0**, commission **0**, transport **0**.
- Award bands table shown; lowest band marked as current.

**Pass / Fail:** ____

---

### POS-02 — Hit 12,500 band + transport

| Step | Action |
|------|--------|
| 1 | As Agent A, post **field** sale(s) on day D totaling **Ksh 12,500** net (full pay same day). No zip / cup-holder lines. |
| 2 | Refresh agent dashboard for day D. |

**Expected**
- Qualifying sales ≈ **12,500**.
- Commission **500**.
- Transport **200** (min sales met).
- “Your band” on the 12,500–19,999.99 row.

**Pass / Fail:** ____

---

### POS-03 — Previous-day query

| Step | Action |
|------|--------|
| 1 | On the commission card, go back one day (chevron or date picker). |
| 2 | Confirm the former day loads (sales/commission for that date only). |
| 3 | Return to today. |

**Expected**
- Past day shows that day’s totals only (not mixed with today).
- Future dates blocked / next disabled on today.

**Pass / Fail:** ____

---

### POS-04 — Top band 50,000+

| Step | Action |
|------|--------|
| 1 | Field sales day D totaling **Ksh 50,000+** (full pay). |
| 2 | Refresh dashboard. |

**Expected**
- Commission **4,000**.
- Transport **200**.
- Top band highlighted; no “sales to go”.

**Pass / Fail:** ____

---

### POS-05 — Payroll month sums daily awards

| Step | Action |
|------|--------|
| 1 | Ensure Agent A has two qualifying days in Month M (e.g. day1 commission 500+200, day2 commission 1000+200). |
| 2 | Create payroll run for Month M → **Calculate**. |
| 3 | Open Agent A payslip. |

**Expected**
- Commission earning ≈ sum of daily commission + transport for the month (e.g. 1,900 in the example).
- Meta / notes indicate `daily_bands` scheme.

**Pass / Fail:** ____

---

### POS-06 — Admin can change the template

| Step | Action |
|------|--------|
| 1 | Payroll → Settings → change a band commission (e.g. 500 → 600). Save. |
| 2 | Reload agent dashboard for a day that sits in that band. |
| 3 | Optionally **Reset to PDF default** and Save. |

**Expected**
- Agent card and payroll use the saved bands.
- Reset restores PDF starter values after Save.

**Pass / Fail:** ____

---

## Negative / exclusion scenarios

### NEG-01 — Shop POS excluded

| Step | Action |
|------|--------|
| 1 | Post a **shop** (non-field) sale for Agent A same day. |
| 2 | Refresh commission card. |

**Expected**
- Shop sale does **not** increase qualifying sales.

**Pass / Fail:** ____

---

### NEG-02 — Partial / unpaid same day excluded

| Step | Action |
|------|--------|
| 1 | Post field sale with amount paid **less than** total. |
| 2 | Refresh commission card. |

**Expected**
- Sale does not count toward qualifying sales.

**Pass / Fail:** ____

---

### NEG-03 — Non-qualifying product keywords (still visible)

| Step | Action |
|------|--------|
| 1 | Field sale including only a **zip** (or sofa cup holder) line, full pay. |
| 2 | Confirm the sale still appears in agent sales / history. |
| 3 | Refresh commission card. |
| 4 | Payroll → Settings: untick “Do not count matching product lines…” (or clear keywords), Save. Re-check the same day. |

**Expected**
- Sale remains visible everywhere.
- With exclusions on: qualifying sales do not include that line; card may show “do not qualify (still on your sales)”.
- With exclusions off / empty keywords: that line counts toward qualifying sales.

**Pass / Fail:** ____

---

### NEG-04 — Feature / setting off

| Step | Action |
|------|--------|
| 1 | Untick Include sales-agent commission (or turn module feature off). |
| 2 | Open agent dashboard. |

**Expected**
- Card shows commission turned off (or no awards).
- Calculate run does not add band commission.

**Pass / Fail:** ____

---

## Integrity checks (must not leak)

| Check | Expected |
|-------|----------|
| Shop POS for the same agent | Does **not** raise qualifying sales / commission |
| Field agent `GET /api/sales/` | Field sales only (shop rows absent); zip lines **still listed** |
| Day cards sum vs payroll month | Same commission + transport total on payslip `EARN_COMMISSION` |
| Zip return with refund line item | Does not reduce kit qualifying sales |

## API smoke

| Call | Expected |
|------|----------|
| `GET /api/payroll/me/commission-day/` | Today’s payload + `template.bands` |
| `GET /api/payroll/me/commission-day/?date=YYYY-MM-DD` | That day’s payload |
| Future date | 400 |
| `GET /api/payroll/settings/` | `sales_commission_template` normalized to daily bands |

---

## Legacy percent (optional)

Only if ops switches template `scheme` to `percent`: monthly net field sales × rate (role / person). Prefer daily bands for go-live.
