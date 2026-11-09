# Analyst take-home assessment

**Role under review:** Sales & collections reporting analyst  
**Purpose:** Prove the candidate can turn POS exports into decisions the owner can use.  
**Candidate turnaround:** One working day from receipt of the data pack.  
**Data window:** One full trading week (seven consecutive days), not a single day.

A one-day file is too thin to show judgement. A week shows pattern, exceptions, and whether the person can separate noise from signal.

---

## Hiring manager — prepare once

1. Choose one closed trading week (Monday–Sunday).  
2. Download these Excels for **that same week** (same date from / date to on every file):
   - Sales history Excel  
   - Payments trail Excel  
   - Product Performance Excel  
   - Optional but recommended: Trading profit gross sales Excel, COGS/goods Excel, Stock valuation Excel  
3. Zip as `Omuwenga_Data_Week_[YYYYMMDD]-[YYYYMMDD].zip`  
4. Send the candidate **only** the section titled **Candidate pack** (below), plus the data zip.  
5. Keep the mark schemes for yourself.

When the return zip arrives, book a 20-minute call: 10 minutes presentation, 10 minutes questions.

---

# Candidate pack

## Role

We are assessing you for a **sales and collections reporting** role.

You will receive Excel exports from our point-of-sale system for **one trading week**.  
You have **one working day** to complete the work and return a single zip file.  
After that, you will present your slides on a short call.

This is not a speed test. Accuracy, clarity, and sound judgement matter more than polish.

## What you will receive

A zip of Excel files for one week. All files cover the **same dates**. Use only those files. Do not invent figures.

Minimum files:

- Sales  
- Payments trail  
- Product Performance  

## Rules

1. Do not alter the original downloads. Build your own answer workbook.  
2. Prefer formulas and Pivot Tables. Do not type a total that a formula can calculate.  
3. Label every important number with its source sheet and column.  
4. If something is missing, write `Not in the data` and continue.  
5. Return **one zip** only. See naming rules at the end.

---

## Part 1 — Excel (`1_Excel_[YourName].xlsx`)

Complete every question. Use the sheet names given.

### Q1 — Week totals (`Q1_Totals`)

1. Total sales for the week  
2. Number of sale tickets  
3. Total units sold (if available; otherwise `Not in the data`)  
4. Average daily sales (total sales ÷ number of days with sales)

Show each result with an Excel formula or Pivot Table. Note the source beside it.

### Q2 — Pattern across the week (`Q2_Daily`)

Build a table: **Date | Sales amount | Ticket count**  
Add a simple line or column chart of daily sales.  
In two sentences on the sheet: which day was strongest, which was weakest, and by how much.

### Q3 — Payment mix (`Q3_Payment`)

Table: **Payment method | Amount | % of week total**  
Use `SUMIF`/`SUMIFS` or a Pivot Table.  
Add a chart. Percentages must reconcile to the week total.

### Q4 — Products (`Q4_Products`)

1. Top 5 products by quantity  
2. Top 5 products by revenue (if revenue exists)  
3. One sentence: do the same products lead both lists? If not, what does that suggest?

### Q5 — Sales versus money received (`Q5_Reconcile`)

| Measure | Amount |
|---------|--------|
| Week sales (Q1) | |
| Week money in (Payments trail) | |
| Difference | |

If the Payments file shows types (for example sale tender vs debt collection), split money in by type.  

Then four bullets maximum: why sales and money received can differ in a real shop week. Base every bullet on the files.

### Q6 — Functions check (`Q6_Functions`)

On this sheet, working examples only:

| Label | Working formula on your data |
|-------|------------------------------|
| SUM | |
| SUMIF or SUMIFS | |
| COUNTIF or COUNTA | |
| IF | |
| XLOOKUP or VLOOKUP | |
| Pivot used (sheet name) | |

---

## Part 2 — Written brief (`2_Report_[YourName].docx` or `.pdf`)

**Length:** one to two pages.  
**Reader:** the shop owner. No jargon.

Required headings, in order:

1. **Title** — Week dates and “Weekly sales & collections brief”  
2. **Executive summary** — five sentences or fewer: what mattered this week  
3. **Sales performance** — totals, daily pattern, top products (figures must match Part 1)  
4. **Collections** — money received by method; tender vs debt collections if split  
5. **Gap analysis** — sales vs money in; what it means for cash and credit  
6. **Three actions for next week** — each line: action, owner, deadline  
7. **Value note** — three to five lines: what you would track every week in this role if hired

No new numbers. If unknown: `Not in the data provided.`

---

## Part 3 — Slides (`3_Slides_[YourName].pptx`)

**Five to seven slides**, this order:

1. Title — name, week, one-line headline  
2. Week sales — total, tickets, strongest/weakest day  
3. Top products  
4. Money in — methods (and types if split)  
5. Sales vs money in  
6. Three actions  
7. Optional — one risk or one data gap  

You will present these on a call. Be ready to open Excel and show the source of any figure we ask for.

---

## Return zip

**Deadline:** end of the next working day after you receive the pack (or the deadline stated in the email).

**Zip name:**

`Omuwenga_Assignment_[YourName]_[WeekStart]-[WeekEnd].zip`

**Contents (only these):**

```
1_Excel_[YourName].xlsx
2_Report_[YourName].docx   (or .pdf)
3_Slides_[YourName].pptx
```

One email. One zip. Incomplete zips are not marked.

---

# Examiner only

## What “good hire” looks like

| Signal | Why it matters |
|--------|----------------|
| Daily pattern called out without being asked soft questions | Sees the week, not a single total |
| Separates sales from collections | Protects cash decisions |
| Actions have owner + deadline | Work leaves the spreadsheet |
| Value note is practical | Understands the job |
| Can defend a number from Excel on the call | Trustworthy under pressure |

## Marks

**Part 1 Excel (100)** — Q1 15 · Q2 15 · Q3 15 · Q4 15 · Q5 25 · Q6 15  
Pass to take seriously: **65**

**Part 2 Report (100)** — Structure 15 · Figures match Excel 30 · Clear prose 20 · Sales ≠ collections 15 · Actions 10 · Value note 10  
Pass: **65**

**Part 3 Call (100)** — Slide discipline 15 · Consistency 25 · Talk 25 · Q&A / Excel defence 25 · Visuals 10  
Shortlist: **70**

**Weighting:** Excel 40% · Report 30% · Presentation 30%  
**Hire bar:** weighted ≥ 70, all three files present, pass marks met.

## Your answer key (15 minutes)

From the same week files: week sales total (A), payments total (B), top SKU by qty (C), strongest day (D).  
Candidate within ~1% on A and B; C and D must match unless a tie is explained.

## Call questions (ask three)

1. Show the formula or pivot for week sales.  
2. Why can week sales exceed money received?  
3. If the owner has two minutes, which slide and why?  
4. What would you add to next week’s pack that these files do not show?

---

## Email to candidate (copy and send)

> Subject: Reporting analyst assessment — one trading week  
>  
> Attached is one week of Excel exports from our POS.  
>  
> You have one working day to complete the assessment and return a single zip:  
> `1_Excel`, `2_Report`, and `3_Slides` as specified in the brief.  
>  
> We are hiring for sales and collections reporting. The week of data is intentional: we need to see pattern, reconciliation, and clear recommendations—not a single-day total.  
>  
> After we receive your zip we will schedule a short presentation call.  
> Use only the files provided. Do not invent numbers.
