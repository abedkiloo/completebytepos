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

`apiBaseUrl`, `formValidation`, `userFormPayload`, `categoryTree`, `apiErrors`, `formatters`, `mediaUrl`, `productStock`, `productPricing`, `setupStatus`, `storeSettingsCache`, `walkInCustomer`, `paymentMethods`, `modulePresets`, `moduleDomains`, `useStoreSettings`, `useProductVariantsEnabled`.

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
