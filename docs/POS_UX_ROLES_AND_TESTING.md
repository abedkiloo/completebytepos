# CompleteByte POS — UX, roles, and test strategy

## Bootstrap users (production-friendly)

| Username | Password (default) | Role | Primary screens |
|----------|-------------------|------|-----------------|
| `admin` | `admin123` | **Super Admin** | Everything: modules, users, settings, full reports |
| `manager` | `manager123` | **Manager** | Products, inventory, POS, billing, reports, expenses — no user/role admin |
| `sales` | `sales123` | **Sales Personnel** | POS, billing, customers; view products only |

Commands (Docker runs these on start):

```bash
python manage.py init_permissions
python manage.py create_users          # bootstrap users only (no products)
python manage.py seed_demo_catalog     # optional: 3 demo SKUs for local testing
```

**Do not** run `populate_test_data` in production — it creates hundreds of users and thousands of products. Use it only in dev when you explicitly need load testing:

```bash
python manage.py populate_test_data --users 5 --products 50
```

## Demo catalog (optional)

Fresh installs do **not** seed products or categories. Add your assortment under **Products** / **Categories**, or run `python manage.py seed_demo_catalog` locally for three sample SKUs.

## POS UX principles (applied to dashboard)

1. **Role-first home** — Sales staff see 2–3 KPIs and large “Start sale” actions; managers see stock alerts; super admin sees full ops + admin shortcuts.
2. **One primary action per persona** — Sales → POS; Manager → POS + inventory; Admin → modules + users when configuring.
3. **Low clutter** — Removed 8 duplicate stat cards and empty chart placeholders; replaced with scannable cards and quick-action grid (Tailwind + shared UI components).
4. **Truthful stock** — POS/Billing always show sellable quantity (parent + variants); checkout validates the same number.
5. **Receipt control** — Billing defaults to preview; print only when the cashier confirms (reduces paper waste and reprints).

## Permission source of truth

- Code: `be/accounts/role_definitions.py`
- Commands: `init_permissions`, `create_users`
- API enforcement: `be/accounts/permissions.py` (`RequirePerm`, `RequireModuleEnabled`)

Legacy roles **Admin**, **Administrator**, and **Cashier** are deactivated on sync; use **Sales Personnel** instead.

## Test coverage target (~90%)

**Current state:** Strong coverage in `products`, `accounts`, `sales` (250+ tests). Several apps still have empty `tests.py` stubs.

**Measure coverage (in Docker):**

```bash
pip install coverage
cd be && coverage run manage.py test && coverage report -m
```

**Phased plan:**

| Phase | Scope | Focus | Status |
|-------|--------|--------|--------|
| 1 | Products UI | Selling price green, status optional | Done |
| 2 | Settings infra | `ModuleSetting`, `SettingsService`, API, hooks | Done |
| 3 | All modules | 87 per-module toggles (8 modules), gated UI + API | Done |
| 4 | Test hardening | Unit + integration + E2E for flag combinations | **Done** — see below |
| 5 | System consistency | Shared settings UI, deduped fetch, impact warnings | **Done** — see below |

### Phase 4 — feature-flag test matrix

Three layers (per original architecture spec):

| Layer | Backend | Frontend |
|-------|---------|----------|
| **Unit** | `settings/tests/test_settings_service.py`, `products/tests/test_product_status_rules.py`, each `*/tests/test_module_settings_phase3.py` | `*Display.test.js`, `moduleSettingsCache.test.js`, `FeatureFlag.test.js`, `hooks/useModuleSettings.test.js` |
| **Integration** | `settings/tests/test_module_settings_api.py`, `settings/tests/test_phase4_integration.py`, `settings/tests/test_settings_architecture.py` | Module settings cards PATCH immediately (manual + E2E) |
| **E2E (Playwright)** | — | `fe/e2e/specs/products.spec.js`, `fe/e2e/specs/module-settings.spec.js` |

**Run Phase 4 suite:**

```bash
# Backend integration + architecture
docker exec completebytepos_backend python manage.py test \
  settings.tests.test_settings_service \
  settings.tests.test_module_settings_api \
  settings.tests.test_settings_architecture \
  settings.tests.test_phase4_integration \
  products.tests.test_module_settings_phase3 \
  sales.tests.test_module_settings_phase3 \
  -v 1

# Frontend unit (flags + hook)
cd fe && npm test -- --watchAll=false \
  --testPathPattern="Display|moduleSettingsCache|FeatureFlag|useModuleSettings|productDisplay|sellingPrice"

# E2E (stack must be running on :3000)
cd fe && npm run test:e2e
```

**Configuration layers** (store vs module vs install):

1. **Module install** — Module Settings page (`ModuleFeature` / `ModuleSettings.is_enabled`)
2. **Module toggles** — System Settings per-module cards (`ModuleSetting` via `SettingsService`)
3. **Store rules** — System Settings store section (`StoreSettings` singleton)

Store rule `hide_entity_status_toggles` overrides all module status flags (backend + frontend).

### Phase 5 — system consistency

Cross-module polish after all toggles shipped:

| Area | Change |
|------|--------|
| **Performance** | `moduleSettingsStore.js` dedupes GET `/api/settings/{module}/` when multiple hooks mount (e.g. POS sales + customers) |
| **UI consistency** | Single `ModuleSettingsCard` + `moduleSettingsCards.js` config replaces eight duplicate settings components |
| **Impact warnings** | Registry `impact: 'high'` on risky keys (delete, permissions, stock validation, checkout rules); badge + confirm in UI; exposed in API |
| **Tests** | `settings/tests/test_phase5_consistency.py`, dedupe test in `useModuleSettings.test.js` |

**Run Phase 5 suite:**

```bash
docker exec completebytepos_backend python manage.py test \
  settings.tests.test_phase5_consistency \
  settings.tests.test_phase4_integration \
  settings.tests.test_settings_architecture \
  -v 1

cd fe && npm test -- --watchAll=false --testPathPattern=useModuleSettings
```

### E2E coverage (Playwright)

| Spec | Coverage |
|------|----------|
| `e2e/specs/smoke-routes.spec.js` | Super-admin route load for all major pages |
| `e2e/specs/pos-smoke.spec.js` | Retail POS grid + discount module toggle |
| `e2e/specs/high-impact-settings.spec.js` | High-impact badge, confirm cancel/accept |
| `e2e/specs/module-settings.spec.js` | Reports tile hides when flag off |
| `e2e/specs/products.spec.js` | Product status column + selling price colour |

**Run full E2E** (stack on `:3000`, admin/admin123):

One-time setup on your Mac (Playwright runs on the **host**, not inside Docker):

```bash
cd fe && npm install
cd fe && npm run test:e2e:install   # downloads Chromium (~150MB)
```

Then with `./run_docker.sh` running:

```bash
cd fe && npm run test:e2e          # all 31 specs
cd fe && npm run test:e2e:smoke    # route + POS smoke (23 specs)
cd fe && npm run test:e2e:settings # module toggles + products (10 specs)
```

Helpers: `e2e/helpers/auth.js` (login), `e2e/helpers/moduleSettings.js` (controlled checkbox click + PATCH wait).

| Phase | Apps | Focus | Status |
|-------|------|--------|--------|
| 1 | `sales`, `products` | Views + services edge cases (holding, stock, wallet) | Done |
| 2 | `inventory`, `reports` | Stock movements, transfer/undo, dashboard API, period filters | **Done** — see test packages below |
| 3 | `expenses`, `income`, `transfers` + persona flows | Service + API tests; three-user E2E | **Done** — `utils/tests/test_three_user_personas.py` |
| 3 | `expenses`, `income`, `accounting`, `transfers` | CRUD + permissions |
| 4 | `settings`, `accounts` | Module flags, bootstrap commands | **Done** — Phase 4 matrix above |

**Test types:**

- **Unit** — `stock_utils`, serializers, service methods
- **Integration** — ViewSets with JWT + tenant/branch
- **Functional** — Full checkout flows (`test_billing_checkout.py` pattern)

Config: `be/.coveragerc`, `coverage` in `be/requirements.txt`.

### Phase 2 test files

| App | Files |
|-----|--------|
| `inventory` | `test_views.py`, `test_views_extended.py`, `test_transfer_undo.py`, `test_services.py` |
| `reports` | `test_views.py`, `test_views_extended.py`, `test_resolve_period.py`, `test_dashboard_api.py` |
| shared | `utils/tests/api_test_base.py`, `settings/test_utils.py` (`enable_multi_branch_support`) |

```bash
docker exec completebytepos_backend python manage.py test

# Frontend role helpers
cd fe && npm test -- --watchAll=false --testPathPattern=roleAccess
```

## Service layer status

| App | Service | View logic moved |
|-----|---------|------------------|
| `reports` | `reports/services.py` — `resolve_period`, `ReportDashboardService` | Dashboard delegates to service |
| `inventory` | `undo_transfer`, `find_paired_transfer_movement` | `undo` action is thin |
| `expenses`, `income`, `transfers` | Already service-driven | Views stay thin |
| `sales` | `SaleService` (large) | `create` still has pre-service validation — **next refactor** |

## Frontend (three personas)

- `fe/src/utils/roleAccess.js` — persona detection, permission check, route guards
- `fe/src/utils/roleAccess.test.js` — Jest unit tests
- `Login.js` stores `profile` + `permissions` for role-aware UI
```

## Edge cases checklist (sales / POS)

- [x] Holding sale excluded from reports but available for checkout/cancel
- [x] Insufficient stock returns field-level validation (not raw list)
- [x] Variants disabled in module settings — POS uses parent product stock
- [x] Walk-in customer default on billing
- [ ] Concurrent checkout on same SKU (race) — consider `select_for_update` in stock deduction
- [ ] Offline / network retry on POS — frontend queue (future)

## Related files

- Dashboard UI: `fe/src/components/Dashboard/Dashboard.js`
- Billing POS: `fe/src/components/POS/billing/`
- Retail POS v2: `fe/src/components/POS/v2/`
