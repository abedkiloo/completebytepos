# Stock Checkpoints — Management Brief

**Product:** CompleteBytePOS  
**Audience:** Operations, Finance, and Store leadership  
**Purpose:** Explain how stock takes work in the system, what decisions managers control, and how inventory stays aligned with sales and accounting.

---

## 1. Executive summary

Stock checkpoints let authorised staff **freeze a point in time**, **count stock at hand**, **correct the system quantity**, and **post the value change to the Inventory ledger**. Each closed checkpoint becomes a **reporting baseline** so sales and inventory reports can start from a known, trusted count.

Managers choose whether a stock take **stops sales** on included products until they are counted, or whether the shop **keeps selling while counting**. That policy has a store-wide default (Module Settings) and can be overridden for each individual stock take.

---

## 2. Business problem this solves

Without a formal stock take process:

- System stock drifts from physical stock (theft, breakage, missed receipts, wrong sales).
- Sales may continue against incorrect quantities, making shortages worse.
- Finance cannot tell when the last trusted count was, so inventory value and profit reports mix “before” and “after” corrections.
- Adjustments happen ad hoc, with weak audit trail.

Stock checkpoints give a repeatable, auditable cycle: **open → count → close**.

---

## 3. How a stock take works

| Step | What happens | Business meaning |
|------|----------------|------------------|
| **Open** | Manager opens a checkpoint with a title (e.g. “March month-end”). Includes all tracked products, or a selected list. Optionally **blocks sales** on those items. | Formal start of the count. System snapshots current quantities and unit costs. |
| **Count** | For each line, staff enter **stock at hand**. The system updates product stock, records a stock movement, and posts an Inventory journal for the value difference. | Physical truth becomes system truth; books move with the count. |
| **Close** | Allowed only when every line is counted. Timestamp and user are stored. | Locked baseline for reports; next “journey” of sales/stock starts from this point. |
| **Cancel** | Abandons an open checkpoint without changing stock. Sell blocks (if any) lift. | Escape hatch if the take was opened by mistake. |

**Access:** Opening, counting, and closing require the **inventory manage** permission. Sales staff do not open checkpoints.

---

## 4. Stopping sales — management control

### 4.1 Store-wide default

**Where:** Module Settings → Inventory → **“Block sales during stock take (default)”**

| Setting | Effect |
|---------|--------|
| **On** (recommended for full stocktakes) | New checkpoints default to stopping sales on included products until each line is counted. |
| **Off** | New checkpoints default to allowing sales while counting (soft count / continuous trade). |

### 4.2 Per stock take override

When opening a checkpoint, the manager can tick or untick:

**“Stop sales on included products until counted”**

- Checked → hard freeze for that take (POS and API reject sales of pending SKUs).
- Unchecked → count proceeds; customers can still buy those products.

Each open checkpoint clearly shows **Sales blocked** or **Sales open** so floor staff know the mode.

### 4.3 When to use which mode

| Mode | Use when | Trade-off |
|------|----------|-----------|
| **Stop sales** | Month-end or audit counts where accuracy matters more than uninterrupted trade | Cleaner count; temporary lost sales / queues on frozen SKUs |
| **Allow sales** | Spot checks, partial counts, or busy trading hours | Trade continues; counts may race with live sales (count notes / timing matter more) |

Recommendation: keep the **default on** (block sales). Turn off only for specific soft counts.

---

## 5. Accounting alignment

When a counted quantity differs from the system snapshot:

1. A **stock adjustment** movement is recorded (reference `CHECKPOINT-{id}`).
2. An **Inventory journal** updates account **1300 (Inventory)** against **6400 (Inventory count variance)** for the value of the difference (quantity × unit cost snapshot).

That keeps the balance sheet inventory value in step with the physical count, instead of leaving stock and books out of sync.

---

## 6. Reporting baselines

- Closing a checkpoint marks a **trusted starting point**.
- Inventory and related reports can use the **latest closed checkpoint** as the period baseline (with admin-visible checkpoint markers on report screens).
- Leadership can ask: “What did we sell and how did stock move **since the last closed stock take**?” rather than mixing pre- and post-correction periods.

---

## 7. Roles and controls

| Role / capability | Typical use |
|-------------------|-------------|
| **Super Admin / Module Settings** | Sets the store default for blocking sales during stock takes |
| **Manager (inventory manage)** | Opens, counts, closes, or cancels checkpoints; chooses block-sales per take |
| **Sales / POS** | Cannot open checkpoints; cannot sell blocked SKUs while a hard freeze is open |
| **Finance / Reports** | Uses closed checkpoints as baselines; sees inventory value after count |

---

## 8. Operational checklist (for store managers)

1. Agree with leadership whether this take should **stop sales** or not.  
2. Open a checkpoint with a clear title and date context.  
3. Count every line (stock at hand). Investigate large variances before closing.  
4. Close the checkpoint only when the count is complete.  
5. Review reports from the new baseline; confirm Inventory account movements look reasonable.  
6. If the take was opened wrongly, **cancel** instead of forcing incorrect counts.

---

## 9. Benefits for the business

- **Control:** Sales freeze is a deliberate policy, not an accident.  
- **Flexibility:** Soft counts during peak hours without shutting the shop.  
- **Accuracy:** Physical stock, system stock, and Inventory GL stay aligned.  
- **Auditability:** Who opened, who counted, who closed, and when.  
- **Clarity in reporting:** Each closed take starts a clean performance journey.

---

## 10. Summary for decision makers

CompleteBytePOS now supports formal, repeating stock takes. Management sets a **default policy** for whether stock takes stop sales, and managers can **override that choice for each take**. Counts update stock and the Inventory ledger, and closed checkpoints become report baselines. That gives operations a practical floor process and finance a trustworthy inventory story.

---

*Internal product note — share with management as a briefing; technical setup lives under Inventory → Stock checkpoints and Module Settings → Inventory.*
