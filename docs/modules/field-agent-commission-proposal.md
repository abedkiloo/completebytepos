# Field sales commission — design proposal

**Status:** Implemented (v2 daily bands = default). See §10–§11 for what shipped.  
**Audience:** Product owner / ops / payroll admin  
**Author stance:** System design for Omuwenga / CompleteBytePOS as it works today  

---

## 0. Current default (Omuwenga PDF starter)

Award template is **daily fixed commission by qualifying sales band**, not a monthly %.  
Stored in `PayrollSettings.sales_commission_template` (editable in Payroll → Settings).  
Agents see the bands + today’s award on the field-sales dashboard (web + app) and can open any previous day.

| Daily qualifying sales (KES) | Commission |
|------------------------------|------------|
| Below 12,500 | 0 |
| 12,500 – 19,999.99 | 500 |
| 20,000 – 31,999.99 | 1,000 |
| 32,000 – 39,999.99 | 2,000 |
| 40,000 – 49,999.99 | 3,500 |
| 50,000 and above | 4,000 |

**Transport:** qualifying sales ≥ 5,000 → **KES 200** for the following working day.  
**Qualifying day:** field sales attributed to the agent, paid in full same day.  
**Non-qualifying products (configurable):** by default product names matching `zip` or `sofa cup holder` do **not** count toward the award base — they are **not** removed from POS or agent sales views. Turn off or edit keywords under Payroll → Settings.  
**Payroll:** sum each day’s band + transport over the calendar month into `EARN_COMMISSION`.  
**Legacy:** set template `scheme` to `percent` to use the older monthly % path.

---

## 1. What we need

Field sales agents should earn **commission on sales**, on top of (or instead of part of) fixed pay.

We need:

1. A **general award template** (daily bands by default; editable by payroll admin).  
2. That template **visible every day** on the sales agent dashboard, with previous-day lookup.  
3. Ability to **change the store-wide template** without a code deploy.  
4. Payslip month total still calculated from the same rules (sum of daily awards).

---

## 2. What we already have (reuse this)

| Piece | Today | Use for commission |
|-------|--------|--------------------|
| **Role pay package** | One package per role (Manager, Sales Personnel, …): basic + component lines | **General template** for Field Sales |
| **Staff pay assignment** | Per employee override of a component | **Person-specific** commission rate or fixed top-up |
| **Employee.salary** | Optional basic override | Keep as today |
| **Payslip run** | Calculate → submit → approve | Commission lands as a payslip earning for the period |
| **Appraisal bonus adapter** | Formula component filled at calculate time from Target Delivery | **Same pattern** for commission (compute from sales, write amount onto payslip) |
| **Sales person report** | Gross / net / collected / field vs shop by `served_by` / cashier | **Proof and base** for commission |
| **Field sales** | `Sale.entry_source = field`, `served_by` = packing agent | Attribute field revenue to the agent |
| **Role: Field Sales** | `ROLE_FIELD_AGENT` | Attach the general package to this role |

We do **not** need a new parallel “commission module” that ignores payroll. Commission is a **payroll earning** driven by **sales facts**.

---

## 3. Proposed operating model

### 3.1 Two layers (general → personal)

```
Role template (general)
   └─ Field Sales package: basic + commission rules + other allowances
         │
         ├─ Agent A  → inherits template
         ├─ Agent B  → inherits template
         └─ Agent C  → inherits template, then personal override (e.g. 4% instead of 3%)
```

Same for Manager (and Sales Personnel):

```
Role template (general)  →  person inherits  →  optional edit for that person only
```

**Rule of precedence (already how payroll works; we keep it):**

1. Person assignment (if active for that component)  
2. Else role package line  
3. Else defaults / zero  

Editing the **role template** changes everyone who has **no** personal override.  
Editing a **person** never changes the template or other people.

### 3.2 Starting commission model (v1 — keep it simple)

**Base for commission (recommended starting choice):**

| Choice | Definition | Why |
|--------|------------|-----|
| **Primary: Net field sales attributed to the agent** | Completed sales where the agent is `served_by` (and preferably `entry_source = field`), in the payroll period, after refunds | Matches field work; uses existing attribution |
| **Optional add-on later: Collections** | Debt collected that period linked to that agent’s customers/sales | Encourages cash in; more design work — **not in v1** |

**Rate:**

- Role template stores a **commission rate %** (e.g. 3% of net field sales).  
- Person can override that % (e.g. star agent 4%, trainee 2%).  
- Cap optional later (max KES per month) — **not required for v1**.

**Formula (v1):**

```
Commission = Net sales in period (for that agent) × Commission rate %
```

Net sales = same idea as Sales Person Report net for that user in the payslip period (start/end of the payroll run).

**Payslip line:**

- New earning component, e.g. `EARN_COMMISSION` (formula / adapter-driven).  
- Amount calculated when the payroll run is **calculated**, like appraisal bonus.  
- Shown on payslip with meta: rate used, sales base, period dates (for audit).

**Who gets it:**

- Employees linked to a user with role **Field Sales** (or any role whose package includes the commission component).  
- Shop cashiers can get a **separate** package later if you want counter commission; v1 focuses on **field agents**.

### 3.3 Starting numbers (suggestion only — you set live rates)

| Item | Starting suggestion |
|------|---------------------|
| Field Sales basic | Align with current Sales Personnel basic, or lower if commission-heavy |
| Commission rate (role default) | 2%–5% of net field sales (pick one default, e.g. **3%**) |
| When paid | Same payroll period as salary (monthly run) |
| Minimum sales for commission | None in v1 (0 sales → 0 commission) |

Lock rates in the role template before go-live; change person rates only when negotiated.

---

## 4. How this feels in the product (same screens, clearer meaning)

| Screen / concept | Meaning after this design |
|------------------|---------------------------|
| **Payroll → Role packages** | “General templates” by role (Manager, Field Sales, …) |
| **Payroll → Staff pay** | “This person’s package” = template + personal edits |
| **Payroll run** | Calculates basic, allowances, **commission**, appraisal bonus (if on), deductions |
| **Reports → Sales by person** | Remains the **proof** sheet for commission disputes |
| **Employees → job role** | Putting someone on Field Sales attaches them to the Field Sales general template |

UI copy change (small): label role packages as **Role templates (general)** and staff pay as **Personal pay (overrides template)**. Behaviour stays the same pattern you already use for Manager.

---

## 5. Changes we will make (when we implement)

Ordered so each step is shippable.

### 5.1 Align language and existing Manager package (no behaviour break)

- Treat existing Manager (and Sales) packages explicitly as **general role templates**.  
- Confirm Staff pay already overrides per person; document that in payroll help text.  
- No data migration required if packages already exist — **clarify product language and admin training**.

### 5.2 Field Sales role template

- Ensure **Field Sales** role has a `RolePayPackage` (create if missing).  
- Seed starter lines: BASIC (as agreed) + **Commission** component on the package.  
- Default commission rate on the role line (e.g. 3%).

### 5.3 Payroll component + adapter

- Add pay component `EARN_COMMISSION` (formula type, like appraisal bonus).  
- Add adapter: for each employee in the run, resolve linked user → pull net (field) sales for the run period → apply rate from person assignment or role template → write amount on payslip.  
- Store calculation meta (base sales, rate, field-only flag) for audit.  
- Feature flag / payroll setting: **Include sales commission** (on/off), same style as appraisal bonus.

### 5.4 Person-level edit

- Reuse `EmployeePayAssignment`: override commission **rate** (or fixed amount if we allow fixed later).  
- Staff pay UI: show commission rate inherited from template; allow edit for that employee.

### 5.5 Attribution rules (must be written into code comments and admin help)

v1 rules:

1. Credit sale to `served_by` if set, else `cashier`.  
2. For Field Sales package, count only `entry_source = field` **or** all attributed sales — **decide at implementation kickoff; recommendation: field-only for Field Sales role**.  
3. Only `status = completed` posted sales; respect refunds the same way Sales Person Report does.  
4. Period = payroll run date range (or calendar month of the run — match how appraisal bonus periods work).

### 5.6 Reporting / proof

- Sales by person report: keep as commission proof (already worded that way on FE).  
- Optional later: “Commission draft” on payslip calculate preview showing base × rate before lock.

### 5.7 Module packaging

- Gate under **Payroll** feature (e.g. `sales_commission`) so packages without the add-on stay off.  
- Do not invent a separate Agents billing module for v1.

### 5.8 Out of scope for v1 (park)

- Commission on collections / repayments  
- Split commission between packer and delivery driver  
- Tiered rates (e.g. 3% up to X, 5% above)  
- Instant payout outside payroll  
- Counter (shop) commission schemes  

These can reuse the same template → person pattern later.

---

## 6. Example (how a month looks)

| Person | Role template | Personal edit | Week/month net field sales | Rate applied | Commission |
|--------|---------------|---------------|----------------------------|--------------|------------|
| Ann | Field Sales 3% | none | 200,000 | 3% | 6,000 |
| Ben | Field Sales 3% | rate 4% | 200,000 | 4% | 8,000 |
| Carol | Field Sales 3% | none | 0 | 3% | 0 |

Manager package unchanged in structure: still general template; if a manager has a personal allowance today, that remains a person override — same model.

---

## 7. Decisions (signed off for v1)

1. **Base:** Field-only net sales (`entry_source=field`), credit `served_by` else `cashier`.  
2. **Default rate:** 3% (`0.0300`) on Field Sales role package + component default.  
3. **Period:** Calendar month of the payroll run (same style as appraisal bonus).  
4. **With basic:** Field Sales package includes optional basic; commission is an extra earning.  
5. **Shop staff:** Field sales only in v1 (shop POS sales excluded from the base).

---

## 8. Success criteria

- Admin sets **one** Field Sales template; new field agents inherit it.  
- Admin changes **one** agent’s rate without touching others.  
- Changing the template updates agents without personal overrides.  
- Payslip shows commission that matches Sales-by-person proof for the same period (within rounding).  
- Manager / existing packages keep working; wording makes “general vs personal” obvious.

---

## 9. How to use (ops)

1. Enable **Payroll → Sales commission** in module features (and keep Payroll module on).  
2. In **Payroll → Settings**, leave **Include field sales commission** checked.  
3. Open **Role templates** → Field Sales package: confirm `EARN_COMMISSION` rate (default 3%).  
4. For a star agent, open **Staff pay** → add/override `EARN_COMMISSION` with a personal **rate** (e.g. `0.05`).  
5. Create the month’s payroll run → **Calculate** → commission lines appear from net field sales × rate.  
6. Use **Sales by person** report as proof for the same calendar month.

---

## 10. What shipped (v1 percent — still available)

| Piece | Location |
|-------|----------|
| Pay component `EARN_COMMISSION` | `payroll/starters.py` |
| Setting `include_sales_commission` | `PayrollSettings` + FE checkbox |
| Module feature `sales_commission` | `settings/module_registry.py` under payroll |
| Adapter (legacy percent) | `payroll/adapters/commission.py` when template `scheme=percent` |
| Rate precedence (percent) | Staff assignment → role package → component default |
| Field Sales package seed | `ensure_field_sales_commission_package()` |
| Calculate wiring | `payroll/services.py` `_calculate_employee` |
| Tests | `payroll/tests/test_sales_commission.py` |

## 11. What shipped (v2 daily bands — default)

| Piece | Location |
|-------|----------|
| Default PDF bands + transport | `payroll/commission_template.py` |
| Template JSON on settings | `PayrollSettings.sales_commission_template` |
| Day qualifying + dashboard payload | `payroll/daily_commission.py` |
| Agent API `GET /api/payroll/me/commission-day/?date=` | `AgentCommissionDayView` |
| Payroll month sum of daily awards | `fetch_employee_daily_band_commission` |
| FE agent card (date nav + bands) | `fe/.../Dashboard/AgentCommissionCard.js` |
| FE settings editor | Payroll → Settings award template table |
| Mobile agent card | `mobile/.../agent_commission_card.dart` on field-sales home |
| Tests | `payroll/tests/test_daily_commission.py` + updated sales commission tests |
