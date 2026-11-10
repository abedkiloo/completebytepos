# Audit trail inventory — modules & actions

**Last reviewed:** after web/mobile `client_channel` + dispatch/delivery/messaging/payments gap fill.  
**Rule:** state-changing actions write an append-only `AuditLog` row; logging failure never blocks the business call. Channel is `web` / `mobile` / `unknown`.

---

## Module coverage (write paths)

| Module | Coverage | How |
|--------|----------|-----|
| **sales / POS / customers / invoicing / debt** | Yes | Mixin CRUD + domain events (checkout, refund, rollback, debt settlement, holding, …) |
| **products / categories / variants / sizes / colors / UoM** | Yes | `AuditedModelViewSetMixin` + approval queue audits |
| **inventory** | Yes | Mixin + `stock_adjust` / `stock_purchase` / `stock_transfer` / `stock_undo` |
| **suppliers** | Yes | Mixin CRUD |
| **employees** | Yes | Mixin CRUD |
| **payroll** | Yes | Settings + components/packages/assignments mixin; run lifecycle verbs |
| **appraisals** | Yes | Policy/update + increment decide → `update` |
| **expenses / income** | Yes | Mixin + expense `approve` |
| **bank accounts / transfers** | Yes | Mixin CRUD |
| **accounting** | Yes | Account types, accounts, journals, transactions mixin |
| **users / roles / auth** | Yes | Create/update/role/password + login/logout/login_failed |
| **settings / modules / tenant / branch** | Yes | Module toggle, features, store settings, presets |
| **daily notes / tasks** | Yes | Author-scoped audited mixin |
| **approvals (maker-checker)** | Yes | `pending_submit` / `approve` / `reject` / `resubmit` |
| **agents (sites / field orders CRUD)** | Yes | Mixin on sites + field orders |
| **CMS / website admin** | Yes | Admin mixins + public enquiry create logged |
| **dispatch** | Yes | `create_driver`, `pack`, `assign` |
| **delivery** | Yes | `arrive`, `start`, `lines_update`, `collect`, `pod`, `complete`, `propose_pin` |
| **messaging** | Yes | Template update/reset + debt reminder queue/send |
| **payments (STK intents)** | Yes | Intent `create`, `stk_push` |
| **reports** | N/A (read) | View-only; no money mutation |
| **audit log itself** | N/A (read) | Append-only; cannot update/delete rows |
| **permission_denied** | Yes | Authenticated 403s via exception handler |

---

## Audit action verbs written to `AuditLog.action`

### Core / security
- `create`, `update`, `delete`
- `login`, `logout`, `login_failed`
- `permission_denied`
- `change_password`, `assign_role`, `assign_permissions`
- `apply_preset`

### Sales / money
- `checkout`, `sale_completed` (via domain helper; source may be create/complete/approval/backfill)
- `holding_save`, `holding_cancel`
- `refund`, `rollback`, `unvoid`, `sale_discarded`, `sale_date_corrected` (date correct uses dedicated helper)
- `debt_settlement_posted`, `debt_settlement_corrected`

### Approvals workflow
- `pending_submit`, `pending_approve`, `pending_reject`, `pending_resubmit`
- `approve`, `reject` (expense approve helper uses `approve`)

### Inventory
- `stock_adjust`, `stock_purchase`, `stock_transfer`, `stock_undo`

### Payroll
- `payroll_run_created`, `payroll_run_calculated`, `payroll_run_submitted`
- `payroll_run_locked`, `payroll_run_rejected`, `payroll_run_cancelled`

### Dispatch / delivery / messaging / payments
- `create_driver`, `pack`, `assign`
- `arrive`, `start`, `lines_update`, `collect`, `pod`, `complete`, `propose_pin`
- `sms_template_update`, `sms_template_reset`
- `sms_debt_reminders_queue`, `sms_debt_reminders_send`
- `stk_push` (plus mixin-style `create` on payment intents)

### Maker-checker *registry* action types (queued change kinds — not always the audit verb)
These identify **what** was proposed; audit rows use the pending_* verbs above:
`product_price`, `product_stock`, `product_deactivate`, `product_delete`, `product_unit`, `product_tax`, `category_deactivate`, `category_delete`, `stock_adjust`, `stock_purchase`, `stock_transfer`, `store_settings`, `payment_methods`, `receipt_legal`, `role_permissions`, `sale_completed_edit`, `sale_refund`, `sale_rollback`, `sale_complete`, `sale_backfill`, `debt_collection`

---

## RBAC permission actions (what roles *may* do)

From `accounts.role_definitions.PERMISSIONS_DATA` — separate from audit verbs; grants access:

**products** view, create, update, delete, approve, export, import  
**categories** view, create, update, delete  
**suppliers** view, create, update, delete, export, manage  
**employees** view, create, update, delete, export, manage  
**appraisals** view, view_all, manage  
**payroll** view, create, update, approve, export, manage, view_own  
**inventory** view, create, update, delete, manage, approve  
**sales** view, create, update, delete, refund, rollback, unvoid, approve, export, daily_sales, view_all  
**agents** view, create, update  
**dispatch** view, update  
**delivery** view, update, history  
**payments** view, create  
**messaging** view, create  
**pos** view, create  
**barcodes** view, create, export  
**reports** view, profit, export  
**customers** view, create, update, delete, export  
**debt_management** view, update, approve, export, payments_trail, correct  
**invoicing** view, create, update, approve, export  
**expenses** view, create, update, delete, approve, export  
**income** view, create, update, delete, approve, export  
**bank_accounts** view, create, update, delete, manage  
*(plus accounting, transfers, users, roles, settings, daily_notes, website, etc. as defined in the same file)*

---

## Intentionally not audited

- Pure **GET** list/detail/dashboard/report reads (noise + performance).
- Anonymous internet probes (403 audit only for **authenticated** denials).
- External Daraja callback itself (system/callback; secured by secret/IP — consider enriching later if needed).

---

## How to verify in the product

1. Perform an action on **web** and on the **app**.
2. Open **Audit log** → filter by module / action / **Web or Mobile app**.
3. Confirm user, time, client channel, and money fields (where applicable).
