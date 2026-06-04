# Testing guide

Architecture for **95% coverage** on business logic (backend services/helpers, frontend utils/config/hooks).

## Test pyramid

| Layer | Backend | Frontend | Purpose |
|-------|---------|----------|---------|
| **Unit** | `<app>/tests/test_*.py` | `src/utils/*.test.js`, `src/hooks/*.test.js` | Fast; rules & helpers |
| **API** | `APITestCase` + `utils/tests/api_test_base.py` | — | HTTP contracts, permissions |
| **E2E** | — | `fe/e2e/specs/*.spec.js` | Critical personas only |

**Rule:** Keep views/components thin; test logic in services (BE) and utils/hooks (FE).

---

## Backend architecture

```
be/
├── testing/
│   ├── coverage_gates.json   # Modules that must stay ≥ 95%
│   ├── check_gates.py
│   └── README.md
├── utils/tests/api_test_base.py   # ManagerAPITestCase, SalesAPITestCase
├── <app>/
│   ├── services.py              # ← primary test target
│   ├── tests/
│   │   ├── test_services.py
│   │   ├── test_views.py
│   │   └── test_*_serializer.py
│   └── …
├── .coveragerc
└── run_tests_coverage.sh
```

### Naming

- File: `test_<subject>.py` under `<app>/tests/`.
- Class: `<Subject>Tests` or `<Subject>APITests`.
- Method: `test_<outcome>_<condition>`.

### Run

```bash
# Docker
docker exec completebytepos_backend python manage.py test
docker exec completebytepos_backend sh -c "cd /app && USE_SQLITE=true ./run_tests_coverage.sh --gates"

# Local (use project venv — Django 4.2)
cd be
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
USE_SQLITE=true ./run_tests_coverage.sh
USE_SQLITE=true ./run_tests_coverage.sh --gates   # enforce 95% on gated packages
```

### Coverage gates (95%)

Gated paths are listed in `be/testing/coverage_gates.json` (config, `user_write`, `catalog_rules`, `*/services.py` for core apps, etc.).

CI runs `./run_tests_coverage.sh --gates` and fails if any package is below **95%**.

| Layer | Target |
|-------|--------|
| Gated logic modules | **≥ 95%** (enforced) |
| Other services / serializers | **≥ 85%** (goal) |
| Views | **≥ 75%** via API tests |
| Migrations, admin, `populate_test_data` | Excluded (`.coveragerc`) |

---

## Frontend architecture

```
fe/src/
├── test-utils/           # Shared mocks (localStorage, render helpers)
├── utils/                # Business rules — **95% gate**
│   ├── foo.js
│   └── foo.test.js       # co-located
├── config/               # apiBaseUrl, env — **95% gate**
├── hooks/                  # useStoreSettings, etc. — **95% gate**
└── components/           # RTL tests sparingly; E2E for flows
```

### Principles

1. Extract logic from components into `utils/` or `hooks/` and test there.
2. Co-locate: `foo.js` + `foo.test.js`.
3. Do **not** gate entire `components/` at 95%; use E2E for pages.

### Run

```bash
cd fe
npm test                              # watch
npm run test:unit                     # utils + config + hooks
npm run test:coverage                 # CI — fails under 95% lines/statements
npm run test:e2e:smoke                # Playwright smoke
```

Jest **`npm run test:coverage`** enforces **≥ 95%** lines/statements on:

`apiBaseUrl`, `formValidation`, `userFormPayload`, `categoryTree`, `apiErrors`, `formatters`, `mediaUrl`, `productStock`, `catalogStock`, `productPricing`, `setupStatus`, `storeSettingsCache`, `walkInCustomer`, `paymentMethods`, `modulePresets`, `moduleDomains`, `posCartRecovery`, `billingCartLine`, `useStoreSettings`, `useProductVariantsEnabled`.

### Catalogue stock (variants off, rows in DB)

When **Product Variants** is disabled but products still have `has_variants` and variant rows, stock may sit on the **parent** and/or **variant** rows. All surfaces must use the same rule: **`max(parent, sum(active variants))`** (`products/stock_utils.py`, FE `catalogStock.js`).

Regression tests: `be/products/tests/test_catalog_stock_consistency.py`, `fe/src/utils/catalogStock.test.js`, `fe/src/utils/moduleFeatures.catalogStock.test.js`.

### Module feature flags (system-wide)

Backend resolver: `be/settings/module_features.py` (registry defaults + DB). API includes `registry.feature_defaults` on `/api/modules/` and login `enabled_modules`. Frontend: `moduleFeatures.js`, `moduleCache.js`, `navAccess.js` — all use the same default when a feature row is missing.

Regression tests: `be/settings/tests/test_module_feature_system_wide.py`, `fe/src/utils/moduleFeatures.variants.test.js`, `fe/src/utils/navAccess.variants.test.js`.

### Sensitive edits & audit log

Sales Personnel cannot change prices, stock levels, tax/discount on drafts, or sale line price overrides. Policy: `be/accounts/sensitive_edits.py`.

**Audit trail (TDD contract):** Every material write should append an `AuditLog` row. Helpers: `be/utils/audit_helpers.py` (`audited_perform_*`, `log_domain_event`). Domain events: `be/utils/audit_events.py` (checkout, holding save/cancel, stock adjust/purchase/transfer/undo, approvals). Viewsets use `AuditedModelViewSetMixin` or explicit `log_domain_event` on custom `@action` handlers. Managers read `/audit-log` and `GET /api/accounts/audit-logs/`.

Run contract tests first when adding a new write path:

```bash
cd be && USE_SQLITE=true venv/bin/python manage.py test \
  accounts.tests.test_audit_trail_writes utils.tests.test_audit_helpers utils.tests.test_audit_events
```

Tests: `be/accounts/tests/test_audit_trail_writes.py`, `be/accounts/tests/test_sensitive_edits.py`, `be/accounts/tests/test_audit_log.py`, `be/utils/tests/test_audit_helpers.py`, `be/utils/tests/test_audit_events.py`, `fe/src/utils/roleAccess.financial.test.js`.

### Maker-checker (two-step approval)

When `StoreSettings.maker_checker_enabled` is true, sensitive product price/stock patches and inventory adjustments create `PendingChange` rows instead of updating live data. Checkers approve via `POST /api/approvals/pending-changes/{id}/approve/` (super admin or user with module `approve`). POS/search serializers expose `pending_approval` flags and keep approved prices/stock for sales.

```bash
cd be && USE_SQLITE=true venv/bin/python manage.py test approvals.tests.test_maker_checker
```

Tests: `be/approvals/tests/test_maker_checker.py` (TDD contract — extend this file before adding new sensitive actions).

**Full program checklist (priorities, matrix, FE backlog):** [MAKER_CHECKER.md](./MAKER_CHECKER.md).

**Do not** add startup scripts that force `product_variants` off after `init_modules` (removed from Docker compose); that overwrote Module Settings toggles on every container restart.

### POS cart recovery

When a cashier leaves POS and returns with items still in the cart:

- **Terminal POS (`/pos/billing`)** — server draft via `GET /api/sales/active-holding/`; prompt before auto-loading.
- **Retail POS (`/pos`)** — `sessionStorage` draft keyed by user + branch (`posCartRecovery.js`).

Tests: `fe/src/utils/posCartRecovery.test.js`, `be/sales/tests/test_active_holding_recovery.py`.

**`npm run test:flags`** runs `*Display.js`, `sessionIdle`, `moduleFeatures`, `navAccess`, `roleAccess`, etc.

**`npm run test:coverage:all`** — full utils report without failing thresholds (for dashboards).

Hooks (`useStoreSettings`, `useProductVariantsEnabled`) are covered by dedicated hook tests; raise hook coverage in a follow-up if you add them to the gate list.

---

## What to add when you change code

| Change | Tests |
|--------|--------|
| Service method | `be/<app>/tests/test_services.py` |
| Serializer validation | `test_*_serializer.py` |
| API endpoint | `test_views.py` + `api_test_base` |
| FE util / payload | `fe/src/utils/<name>.test.js` |
| New hook | `fe/src/hooks/<name>.test.js` |

---

## CI

GitHub Actions workflow `.github/workflows/tests.yml`:

- **backend:** `USE_SQLITE=true ./run_tests_coverage.sh --gates`
- **frontend:** `npm run test:coverage`

---

## Related

- [POS_UX_ROLES_AND_TESTING.md](./POS_UX_ROLES_AND_TESTING.md) — personas, E2E
- [SETUP.md](./SETUP.md) — Docker commands
