# Maker-checker program tracker

Single checklist for two-step approval: what exists, what’s next, and how we avoid gaps.  
**Rule:** add or extend a test in `be/approvals/tests/test_maker_checker.py` (or a focused module test) **before** wiring a new action.

**Enable:** `StoreSettings.maker_checker_enabled` (API: store settings PATCH / System Settings UI when built).  
**Emergency stock bypass:** `StoreSettings.emergency_stock_mode` (positive adjusts only).

**API (checker):**

| Endpoint | Purpose |
|----------|---------|
| `GET /api/approvals/pending-changes/` | All proposals (checker only) |
| `GET /api/approvals/pending-changes/pending/` | Pending queue |
| `GET /api/approvals/pending-changes/{id}/` | Detail |
| `POST /api/approvals/pending-changes/{id}/approve/` | Apply to live data |
| `POST /api/approvals/pending-changes/{id}/reject/` | Discard (`rejection_reason` required) |

**Maker response when queued:** HTTP **202** + `message` + `pending_change` (+ `product` on product PATCH).

---

## Priority roadmap

| Phase | Goal | Exit criteria |
|-------|------|----------------|
| **P0 — Foundation** | Core model + product price/stock + adjust + POS safe | All P0 rows ✅ in matrix below |
| **P1 — Inventory & catalog** | Purchase, transfer, delete/deactivate, variants | P1 tests green + wired |
| **P2 — Financial & access** | Store settings, payments, receipt legal, roles | ✅ P2 tests green + wired (rows 21–25) |
| **P3 — Sales (optional)** | Post-completion metadata only; refunds/promos deferred | Optional flag off by default |
| **P4 — Frontend** | Maker message + checker queue UI + settings toggles | E2E smoke on staging |
| **P5 — Hardening** | Reports contract, retroactive policy, monitoring | Doc + tests for “no retroactive” |

---

## Master matrix (do not skip rows)

Legend: **✅ Done** · **🔶 Partial** · **⬜ Not started** · **—** N/A or deferred

| # | Sensitive action | Registry action | Live write blocked? | BE wired | TDD test | Audit (`approvals`) | POS / reports use approved only | FE maker UX | FE checker UX |
|---|------------------|-----------------|---------------------|----------|----------|---------------------|----------------------------------|-------------|---------------|
| **P0 — Foundation** |
| P0 BE | Product delete / deactivate / neg-stock tests | — | — | ✅ | ✅ (18 tests) | — | — | — | — |
| F1 | Enable / disable MC globally | — | — | ✅ `StoreSettings` fields | ✅ toggle test | — | — | ✅ System Settings | — |
| F6 | Shared inventory MC helper | — | — | ✅ `inventory_integration.py` | ✅ | — | — | — | — |
| F2 | Pending change CRUD queue | — | — | ✅ `PendingChange` + API | ✅ API approve/reject | ✅ submit/approve/reject | — | — | ✅ `/pending-approvals` |
| F3 | Maker cannot approve own change | — | — | ✅ `user_may_approve_change` | ✅ | — | — | — | — |
| F4 | Batch approve/reject atomic | `batch_id` | — | ✅ service | ✅ multi-action product patch | — | — | ✅ bulk adjust modal | ⬜ batch approve UI |
| F5 | Reason required on propose | — | — | ✅ | ✅ (implicit in 202 tests) | ✅ in `changes.reason` | — | ✅ `ChangeReasonField` on forms | — |
| **P0 — Product** |
| 1 | Price / MRP / cost change | `product_price` | ✅ | ✅ PATCH + `submitted_keys` | ✅ | ✅ | ✅ search/list flags | ✅ reason + 202 toast | ✅ queue row |
| 2 | Tax rate change | `product_tax` | ✅ | ✅ same PATCH path | ✅ | ✅ | ⬜ confirm tax on POS | ✅ ProductForm | ✅ queue row |
| 3 | Stock fields on product | `product_stock` | ✅ | ✅ PATCH | ✅ sellable cap test | ✅ | ✅ flags | ✅ ProductForm | ✅ queue row |
| 4 | Deactivate product | `product_deactivate` | ✅ | ✅ PATCH `is_active=false` | ✅ | ✅ | ✅ still sellable until approved | ✅ ProductForm | ✅ queue row |
| 5 | Delete product | `product_delete` | ✅ | ✅ DELETE → 202 | ✅ | ✅ | ✅ row until approve | ✅ delete dialog + reason | ✅ queue row |
| 6 | Unit / conversion change | `product_unit` | ✅ | ✅ PATCH `unit` | ✅ | ✅ | ⬜ | ✅ ProductForm | ✅ queue row |
| 7 | Non-sensitive product fields (name, etc.) | — | — | ✅ immediate | ✅ | ✅ (audit via product write) | — | — | — |
| **P0 — Inventory** |
| 8 | Manual stock adjust | `stock_adjust` | ✅ | ✅ `adjust` → 202 | ✅ | ✅ | ✅ stock unchanged until approve | ✅ adjust modal | ✅ queue row |
| 9 | Stock purchase | `stock_purchase` | ✅ | ✅ `purchase` → 202 | ✅ | ✅ | ✅ | ✅ purchase modal | ✅ queue row |
| 10 | Stock transfer | `stock_transfer` | ✅ | ✅ `transfer` → 202 | ✅ | ✅ | ✅ | ✅ transfer modal | ✅ queue row |
| 11 | Bulk adjust | `stock_adjust` | ✅ | ✅ `bulk_adjust` batch | ✅ | ✅ | ✅ | ✅ bulk modal | ✅ queue row |
| 12 | Movement undo | — | — | ⬜ | ⬜ | 🔶 inventory audit only | — | — | — |
| 13 | Emergency positive stock add | — | bypass MC | ✅ `emergency_stock_mode` | ✅ | ✅ movement audit | — | ⬜ admin toggle | — |
| **P0 — POS & reports** |
| 14 | POS price = approved only | — | — | ✅ `effective` + serializers | ✅ search test | — | ✅ | ✅ POS tile badges | — |
| 15 | Pending stock not in sellable qty | — | — | ✅ `approved_sellable_stock_quantity` | ✅ sale + list test | — | ✅ | ✅ capped `stock_quantity` in API | — |
| 16 | Reports ignore pending | — | — | 🔶 no report reads pending | ✅ sale total test | — | ✅ | — | — |
| 17 | Extreme price approval gate | — | — | ✅ 50% + `extreme_price_confirmed` | ✅ | — | — | — | ✅ confirm on approve |
| 18 | Negative stock block on approve | — | — | ✅ validate | ✅ adjust approve blocked | — | — | — | — |
| **P1 — Catalog extensions** |
| 19 | Variant price/stock | `product_*` | ✅ | ✅ variant viewset | ✅ | ✅ | ✅ sellable cap | ✅ ProductVariantsPanel | ✅ queue row |
| 20 | Category delete / deactivate | `category_*` | ✅ | ✅ category viewset | ✅ | ✅ | ✅ stays active until approve | ✅ Categories + form | ✅ queue row |
| **P2 — Financial & settings** |
| 21 | Store settings PATCH | `store_settings` | ✅ | ✅ `store_settings` view | ✅ P2 tests | ✅ | — | ✅ System Settings | ✅ queue row |
| 22 | Payment methods JSON | `payment_methods` | ✅ | ✅ settings integration | ✅ P2 tests | ✅ | POS methods | ✅ System Settings | ✅ queue row |
| 23 | Receipt footer legal text | `receipt_legal` | ✅ | ✅ settings integration | ✅ P2 tests | ✅ | receipts | ✅ System Settings | ✅ queue row |
| 24 | Module / feature toggles | `module_settings` | ✅ | ✅ module settings PATCH | ✅ P2 tests | ✅ | — | ✅ ModuleSettingsCard | ✅ queue row |
| **P2 — Access control** |
| 25 | Role permission assign | `role_permissions` | ✅ | ✅ role update / assign | ✅ P2 tests | ✅ | — | ✅ RoleForm | ✅ queue row |
| 26 | User create / role assign | — | ⬜ | ⬜ | ⬜ | ✅ user create audit | — | ⬜ | ⬜ |
| 27 | Grant refund/void (sales) | — | ⬜ | ⬜ | ⬜ | ⬜ | — | ⬜ | ⬜ |
| **P2 — Already separate approval flows** |
| 28 | Expenses | — | own `status` | ✅ + MC gate | ✅ `test_financial_workflow` | ✅ audit trail | ✅ stats pending only | ✅ reason + self-approve block | ✅ approve UI |
| 29 | Income | — | own `status` | ✅ + MC gate | ✅ financial workflow tests | ✅ | — | ✅ reason + self-approve block | ✅ approve UI |
| 30 | Money transfer | — | own `status` | ✅ + MC gate | ✅ financial workflow tests | ✅ | — | ⬜ (API only) | ✅ approve via API |
| **P3 — Sales (optional — off by default)** |
| 31 | Edit completed sale (notes/payment) | `sale_completed_edit` | ✅ when flag on | ✅ optional integration | ✅ P3 tests | ✅ | totals unchanged | ✅ System Settings flag | ✅ queue row |
| 32 | Refund / void | — | — | ✅ `POST …/refund/` | ✅ refund tests | ✅ audit `refund` | stock return | ✅ Sales UI | — |
| 33 | Discount rules at POS | — | — | — deferred | — | — | — | — | — |
| 34 | Cashier price override | — | log only (exception) | — deferred | — | — | — | — | — |
| **P3 — Policy** |
| 35 | No retroactive report changes | — | — | ✅ completed sales immutable | ✅ P3 tests | — | — | — | — |
| 36 | Legal retroactive (double approval) | — | — | — deferred | — | — | — | — | — |

---

## Behaviour rules checklist (spec → implementation)

| Rule | Status | Where enforced |
|------|--------|----------------|
| Propose → `pending_approval`, not live | ✅ | `submit_change`, product `update`, inventory `adjust` |
| `made_by`, `made_at`, `proposed_values`, `original_values`, `reason` | ✅ | `PendingChange` model |
| Checker approve → apply live + `approved_by/at` | ✅ | `approve_change` + `apply.py` |
| Checker reject → live unchanged + `rejection_reason` | ✅ | `reject_change` |
| No partial batch approve | ✅ | `batch_id` loop in service |
| Maker sees “not yet active” | ✅ | API 202 + `PENDING_APPROVAL_MESSAGE` toast + badges |
| POS uses old price until approved | ✅ | DB unchanged + serializers |
| Pending delete: still sellable until approved | 🔶 | not deleting until approve — test ⬜ |
| Historical reports unchanged | 🔶 | completed sales immutable; test ✅ one case |
| Approve blocked: negative stock | ✅ | `validate_before_approval` |
| Approve blocked: extreme price without confirm | ✅ | 50% rule |
| POS override: log + limits (exception) | — | deferred (not MC) |
| Post-completion sale edits | — | optional `maker_checker_sales_controls` (default off) |
| Emergency stock: bypass + audit | 🔶 | bypass ✅; audit via movement ⬜ |

---

## TDD workflow (per new row in matrix)

1. Add test class/method in `be/approvals/tests/test_maker_checker.py` (name: `test_<action>_pending_then_approve`).
2. Run — expect **FAIL**.
3. Wire BE: registry (if new action) → integration hook in view/service → `apply.py` handler.
4. Run — **PASS**.
5. Update this doc: change ⬜ → ✅ in matrix.
6. FE: maker `reason` + 202 handling; checker row in queue.

```bash
cd be && USE_SQLITE=true venv/bin/python manage.py test approvals.tests.test_maker_checker -v 1
```

---

## Suggested sprint order (next 2–3 weeks)

1. **P1 polish** — batch approve UI for shared `batch_id`; POS tax confirm on pending tax.
2. **P3 optional** — enable `maker_checker_sales_controls` per future client; refunds/promos still deferred.
3. **Future** — refund/void model, discount rules, POS override logging (rows 32–34, 36).

---

## Code map (quick navigation)

| Area | Path |
|------|------|
| Action registry | `be/approvals/registry.py` |
| Submit / approve / reject | `be/approvals/service.py` |
| Apply to live | `be/approvals/apply.py` |
| POS-safe reads | `be/approvals/effective.py` |
| Product hook | `be/products/views.py` `update()` |
| Inventory hook | `be/inventory/views.py` `adjust()` / `purchase()` / `transfer()` / `bulk_adjust()` |
| Inventory helper | `be/approvals/inventory_integration.py` |
| API | `be/approvals/views.py`, `be/approvals/urls.py` |
| Contract tests | `be/approvals/tests/test_maker_checker.py` |
| Toggle fields | `be/settings/models.py` (`maker_checker_enabled`, `emergency_stock_mode`, `maker_checker_sales_controls`) |
| Optional sales P3 | `be/approvals/sales_policy.py`, `sales_integration.py`, `be/sales/views.py` |

---

## Frontend backlog (structured)

| Screen / flow | Maker | Checker |
|---------------|-------|---------|
| System Settings | Toggle MC + emergency mode | — |
| Products edit | `reason` field; on 202 show toast + pending badge | — |
| Products list | `pending_approval` chips | Link to queue filtered by product |
| Inventory adjust/purchase/transfer | `reason`; handle 202 | — |
| **Approvals** (`/pending-approvals`) | — | Table: type, entity, diff, approve/reject, extreme price confirm |
| POS product search | Badge “pending price” | — |
| Store settings | Reason on save when MC on | Queue row |

---

## Permissions

| Permission | Purpose |
|------------|---------|
| `products.approve` | Checker for product actions |
| `inventory.approve` | Checker for stock actions |
| `settings.approve` | Checker for store settings + API queue |
| Manager role | Gets approve on products/inventory via `sync_default_roles` (not settings until in `_manager_queryset`) |

**Gap:** Manager may need `settings.view` + `settings.approve` for queue API — verify when building FE (super admin always OK).

---

## Related docs

- [TESTING.md](./TESTING.md) — audit + MC test commands  
- Expenses/income/transfers — separate status-based approval (row 28–30); do not duplicate unless unifying under `PendingChange` later.

---

*Last updated: P3 optional sales controls (off by default); refunds/promotions deferred.*
