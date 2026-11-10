# Field sales commission — QA test script

**How to use:** Work top to bottom. For each case: do the steps → check Expected → mark Pass/Fail.  
**Formula under test:** `Commission = Net field sales × rate` for the payroll calendar month.  
**Field sales only:** shop POS sales must not count.  
**Credit to:** `served_by` if set, else `cashier`.

---

## 0. One-time setup (do before any case)

| Step | Action |
|------|--------|
| 0.1 | Log in as **Admin / Super Admin**. |
| 0.2 | Confirm **Payroll** module is on. |
| 0.3 | Confirm module feature **Payroll → Sales commission** is **on**. |
| 0.4 | Open **Payroll → Settings**. Tick **Include field sales commission**. Save. |
| 0.5 | Open **Payroll → Role packages** (role templates). Open **Field Sales**. |
| 0.6 | Confirm line **Sales commission** (`EARN_COMMISSION`) rate = **0.03** (3%). |
| 0.7 | For **commission-only** agents: leave package **default basic** blank; leave employee **salary** blank. |
| 0.8 | Create (or pick) test users: |
| | **Agent A** — Field Sales, linked Employee, **no** personal commission override. |
| | **Agent B** — Field Sales, linked Employee (for override / attribution tests). |
| | **Cashier C** — shop cashier (not Field Sales), for shop-sale exclusion. |
| 0.9 | Pick a clean payroll month (e.g. a future test month, or a month with no other payroll run). Call it **Month M**. |
| 0.10 | Keep **Sales by person** report ready as proof for Month M. |

**Pass setup when:** Field Sales package has 3% commission; Agents A & B exist with linked users; setting is on.

---

## Positive scenarios — how to test

### POS-01 — Role rate applies (3%)

**Goal:** Agent with no personal override gets package rate.

| Step | Action |
|------|--------|
| 1 | As Agent A (or admin posting for A), create **field** sale(s) in Month M totaling **Ksh 100,000** net. Note: `entry_source = field`, served_by / cashier = Agent A. |
| 2 | Confirm Agent A has **no** Staff pay line for Sales commission. |
| 3 | Open **Payroll → Runs**. Create run for Month M (if none). |
| 4 | Click **Calculate**. |
| 5 | Open Agent A’s payslip. |

**Expected**
- Commission line = **Ksh 3,000** (100,000 × 3%).
- Meta / notes show rate ~3%, sales base ~100,000, source = role package.

**Pass / Fail:** ____

---

### POS-02 — Personal rate overrides template

**Goal:** Staff pay rate beats role package.

| Step | Action |
|------|--------|
| 1 | Open **Payroll → Staff pay** → Agent A. |
| 2 | Add / edit **Sales commission** with rate **0.05** (5%). Save. |
| 3 | Ensure Agent A has field sales **Ksh 100,000** in Month M (reuse POS-01 data or new month). |
| 4 | Recalculate payroll run for that month. |
| 5 | Open Agent A payslip. Optionally check Agent B still on 3% if B has same sales base and no override. |

**Expected**
- Agent A commission = **Ksh 5,000**.
- Rate source = assignment / personal.
- Agent B (if tested) still uses **3%**.

**Pass / Fail:** ____

---

### POS-03 — Commission-only (no basic salary)

**Goal:** Field agent with no basic still gets commission.

| Step | Action |
|------|--------|
| 1 | Open Agent A employee record. Clear **salary** (leave empty). |
| 2 | Field Sales role package: clear **default basic**. |
| 3 | Staff pay: ensure **no BASIC** personal line. |
| 4 | Agent A field sales Month M = **Ksh 200,000**. Rate = 3% (remove personal 5% if left from POS-02). |
| 5 | Calculate run. Open payslip. |

**Expected**
- Basic = **0** (or blank / zero).
- Commission = **Ksh 6,000**.
- Net pay driven by commission (minus any deductions only).

**Pass / Fail:** ____

---

### POS-04 — Multiple field sales same month

**Goal:** Sales in the same month add up.

| Step | Action |
|------|--------|
| 1 | In Month M, post two field sales for Agent A: **80,000** and **20,000**. |
| 2 | Calculate payroll. |

**Expected**
- Sales base = **100,000**.
- Commission at 3% = **3,000**.

**Pass / Fail:** ____

---

### POS-05 — Credit via `served_by`

**Goal:** Packing / serving agent gets the sale, not the till user.

| Step | Action |
|------|--------|
| 1 | Create field sale total **50,000**: `served_by` = **Agent A**, cashier = **Cashier C** (or Agent B). |
| 2 | Calculate Month M. |

**Expected**
- Commission base includes **50,000** for **Agent A**.
- Cashier C / Agent B does **not** get that 50,000 in their commission base.

**Pass / Fail:** ____

---

### POS-06 — Credit via cashier when served_by blank

**Goal:** Fallback attribution.

| Step | Action |
|------|--------|
| 1 | Create field sale **40,000** with **served_by empty**, cashier = **Agent A**. |
| 2 | Calculate. |

**Expected**
- **40,000** counts for Agent A.

**Pass / Fail:** ____

---

### POS-07 — Template rate change updates non-override agents

**Goal:** Editing role package changes inheritors only.

| Step | Action |
|------|--------|
| 1 | Ensure Agent A has **no** personal commission rate. |
| 2 | Role package Field Sales: change commission rate **0.03 → 0.04**. Save. |
| 3 | Agent A has field sales **100,000** in the test month. Recalculate. |

**Expected**
- Agent A commission = **4,000**.

**Pass / Fail:** ____  
*(Reset package to 0.03 after this case unless next cases need 4%.)*

---

### POS-08 — Template change does not overwrite personal rate

**Goal:** Personal override is sticky.

| Step | Action |
|------|--------|
| 1 | Staff pay Agent A: commission rate **0.05**. |
| 2 | Role package: set rate to **0.04**. |
| 3 | Agent A field sales **100,000**. Recalculate. |

**Expected**
- Agent A still **5,000** (5%), not 4,000.

**Pass / Fail:** ____

---

### POS-09 — Zero sales → zero commission

**Goal:** No fake commission.

| Step | Action |
|------|--------|
| 1 | Pick Agent B with **no** field sales in Month M (or use a quiet month). |
| 2 | Calculate run including Agent B. |

**Expected**
- Commission **0** (no earning line, or zero).
- No error blocking the run.

**Pass / Fail:** ____

---

### POS-10 — Payslip shows audit meta

**Goal:** Admin can see how commission was built.

| Step | Action |
|------|--------|
| 1 | After any successful calculate with commission > 0, open the payslip / calculation detail for that agent. |

**Expected**
- Visible: sales base, rate (or %), period (year-month), and ideally rate source.

**Pass / Fail:** ____

---

### POS-11 — Proof matches Sales by person

**Goal:** Dispute-proof.

| Step | Action |
|------|--------|
| 1 | Note Agent A commission sales base from payslip (e.g. 150,000) and rate (e.g. 3%). |
| 2 | Open **Reports → Sales by person** (or equivalent) for the **same calendar month**. |
| 3 | Filter / find Agent A **field** net sales. |
| 4 | Compute: report net × rate. Compare to payslip commission. |

**Expected**
- Match within **Ksh 0.01** rounding.

**Pass / Fail:** ____

---

### POS-12 — Approve flow keeps commission

**Goal:** Commission survives submit/approve.

| Step | Action |
|------|--------|
| 1 | Calculate run with known commission (e.g. 3,000). |
| 2 | Submit run. |
| 3 | Approve run. |
| 4 | Re-open Agent A payslip. |

**Expected**
- Commission amount unchanged after approve.

**Pass / Fail:** ____

---

### POS-13 — New Field Sales hire inherits template

**Goal:** New agents get package without manual commission setup.

| Step | Action |
|------|--------|
| 1 | Create new user + employee, role **Field Sales**, link user ↔ employee. |
| 2 | Do **not** add Staff pay commission line. |
| 3 | Post field sales **100,000** in Month M for the new agent. |
| 4 | Calculate. |

**Expected**
- Commission = **3,000** (or current package rate × base).

**Pass / Fail:** ____

---

## Negative scenarios — how to test

### NEG-01 — Shop POS sale excluded

| Step | Action |
|------|--------|
| 1 | As Agent A, complete a **shop / POS** sale (not field) for **99,999**. |
| 2 | Ensure Agent A has **no** field sales that month (or note field total separately). |
| 3 | Calculate. |

**Expected**
- Shop **99,999** is **not** in commission base.
- Commission only from field net (0 if no field sales).

**Pass / Fail:** ____

---

### NEG-02 — Incomplete / non-completed sale excluded

| Step | Action |
|------|--------|
| 1 | Create a field sale that is **not** completed/posted (draft, holding, pending approval if applicable). Total large amount. |
| 2 | Calculate. |

**Expected**
- That sale **not** in commission base until completed/posted per product rules.

**Pass / Fail:** ____

---

### NEG-03 — Wrong month excluded

| Step | Action |
|------|--------|
| 1 | Post field sale **100,000** dated in **Month M−1**. |
| 2 | Create/calculate payroll for **Month M** only. |

**Expected**
- Month M commission does **not** include the M−1 sale.

**Pass / Fail:** ____

---

### NEG-04 — Module feature off

| Step | Action |
|------|--------|
| 1 | Turn **off** Payroll feature **sales_commission**. |
| 2 | Agent A has field sales **100,000** in month. Calculate. |

**Expected**
- Commission **0** / not applied.
- Turn feature back **on** after the case.

**Pass / Fail:** ____

---

### NEG-05 — Setting “Include field sales commission” off

| Step | Action |
|------|--------|
| 1 | Feature on. Open Payroll Settings. **Untick** Include field sales commission. Save. |
| 2 | Calculate with field sales present. |

**Expected**
- Commission **0** / skipped.
- Re-tick setting after the case.

**Pass / Fail:** ____

---

### NEG-06 — Employee with no linked user

| Step | Action |
|------|--------|
| 1 | Create / use employee on Field Sales package **without** linked login user. |
| 2 | Include in payroll calculate (if system allows). |

**Expected**
- Commission **0**.
- No crash; reason effectively “no user”.

**Pass / Fail:** ____

---

### NEG-07 — Non–Field Sales / no commission package line

| Step | Action |
|------|--------|
| 1 | Cashier C (shop role, no EARN_COMMISSION on package) has shop and/or field activity. |
| 2 | Calculate. |

**Expected**
- No field-sales commission earning for Cashier C (unless their role package was given the component on purpose).

**Pass / Fail:** ____

---

### NEG-08 — Sale attributed to another agent

| Step | Action |
|------|--------|
| 1 | Field sale **50,000**, served_by = **Agent B**. |
| 2 | Calculate. Check Agent A and Agent B. |

**Expected**
- Counts for **B** only, not A.

**Pass / Fail:** ____

---

### NEG-09 — Refund reduces commission base

| Step | Action |
|------|--------|
| 1 | Field sale Agent A **100,000** in Month M. |
| 2 | Post refund **20,000** on that sale in the **same month**. |
| 3 | Calculate. |

**Expected**
- Base = **80,000**.
- At 3% → commission **2,400**.

**Pass / Fail:** ____

---

### NEG-10 — Refunds larger than sales → base floors at 0

| Step | Action |
|------|--------|
| 1 | Arrange month where refunds on Agent A’s field sales exceed gross (or equal edge). |
| 2 | Calculate. |

**Expected**
- Sales base **0** (not negative).
- Commission **0**.

**Pass / Fail:** ____

---

### NEG-11 — Discarded / voided sale excluded

| Step | Action |
|------|--------|
| 1 | Create then **discard/void** a field sale for Agent A. |
| 2 | Calculate. |

**Expected**
- Not in commission base.

**Pass / Fail:** ____

---

### NEG-12 — Rate missing / zero

| Step | Action |
|------|--------|
| 1 | Temporarily clear commission rate on package and remove personal assignment (or set rate 0). |
| 2 | Agent has field sales. Calculate. |

**Expected**
- Commission **0**.
- Restore 3% after test.

**Pass / Fail:** ____

---

### NEG-13 — Accidental basic inheritance

**Goal:** Confirm commission-only setup isn’t secretly paying basic.

| Step | Action |
|------|--------|
| 1 | Set Field Sales package **default basic = 15,000**. Leave employee salary empty. |
| 2 | Calculate. |
| 3 | Then clear default basic again and recalculate. |

**Expected**
- With default basic 15,000 → payslip basic **15,000** (fail for “commission-only” intent).
- After clearing default basic + empty salary → basic **0**, commission still from sales.

**Pass / Fail:** ____

---

### NEG-14 — Other role’s shop sales don’t feed field commission

| Step | Action |
|------|--------|
| 1 | Manager / shop user posts large shop sales. |
| 2 | Calculate field agents. |

**Expected**
- Those shop sales do not inflate Field Sales commission bases.

**Pass / Fail:** ____

---

### NEG-15 — Recalculate does not double commission

| Step | Action |
|------|--------|
| 1 | Calculate run → note Agent A commission (e.g. 3,000). |
| 2 | Calculate again with **no new sales**. |

**Expected**
- Same amount (still 3,000), not 6,000.

**Pass / Fail:** ____

---

## Commission-only checklist (run after POS-03)

| Check | How | Pass if |
|-------|-----|---------|
| Employee salary | Employees → Agent A | Empty |
| Package default basic | Role packages → Field Sales | Empty |
| Staff BASIC line | Staff pay → Agent A | Not set |
| Payslip | After calculate | Basic 0, commission = sales × rate |
| Zero-sales peer | Agent with 0 field sales | Commission 0 |

---

## Suggested run order (half day)

1. Setup **0.1–0.10**  
2. **POS-03** (commission-only) → **POS-01** → **POS-02**  
3. **NEG-01**, **NEG-03**, **NEG-09**  
4. **NEG-04**, **NEG-05**  
5. **POS-11** (proof)  
6. **NEG-13**, **NEG-15**  
7. **POS-12** (approve)

---

## Sign-off

| Criterion | Pass? |
|-----------|-------|
| Commission-only agent: basic 0 + commission correct | |
| Shop sales never inflate commission | |
| Personal rate beats template; template doesn’t overwrite personal | |
| Feature/setting off → no commission | |
| Payslip matches Sales-by-person proof for same month | |

**Tester:** _________________ **Date:** ________ **Environment:** ________  

**Overall:** Pass / Fail / Pass with notes: _________________________________
