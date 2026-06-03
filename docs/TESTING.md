# Testing guide

How tests are organised, how to run them, and coverage targets.

## Test pyramid

| Layer | Backend | Frontend | Purpose |
|-------|---------|----------|---------|
| **Unit** | `*/tests/test_*.py` for services, serializers, helpers | `src/utils/*.test.js`, `src/config/*.test.js` | Fast, no UI; business rules |
| **API** | `APITestCase` / `TransactionTestCase` + `APIClient` | — | HTTP contracts, permissions |
| **E2E** | — | `fe/e2e/specs/*.spec.js` (Playwright) | Full flows in browser |

Prefer **unit tests** for pure logic; **API tests** for endpoints; **E2E** for critical personas only.

---

## Backend layout

```
be/
├── utils/tests/
│   └── api_test_base.py      # ManagerAPITestCase, SalesAPITestCase, …
├── accounts/
│   ├── user_write.py         # prepare_user_write_data, apply_profile_updates
│   └── tests/
│       ├── test_user_write.py
│       └── test_user_profile_update.py
├── products/tests/
│   ├── test_services.py
│   ├── test_category_serializer.py
│   └── …
└── .coveragerc
```

### Naming

- File: `test_<subject>.py` under app `tests/` package.
- Class: `<Subject>Tests` or `<Subject>APITests`.
- One behaviour per test method; name describes outcome (`test_update_without_password_succeeds`).

### Run (Docker)

```bash
# All tests
docker exec completebytepos_backend python manage.py test

# One app
docker exec completebytepos_backend python manage.py test accounts.tests

# With coverage
docker exec completebytepos_backend coverage run manage.py test
docker exec completebytepos_backend coverage report -m
docker exec completebytepos_backend coverage html   # htmlcov/
```

### Run (local SQLite)

```bash
cd be
USE_SQLITE=true python manage.py test accounts.tests products.tests
USE_SQLITE=true coverage run manage.py test accounts.tests
USE_SQLITE=true coverage report -m
```

Or: `./run_tests_coverage.sh [module]`

### Coverage targets (backend)

| Area | Target | Notes |
|------|--------|--------|
| `accounts/user_write.py`, `products/serializers` (category) | **≥ 95%** | Pure write/validation logic |
| `*/services.py` | **≥ 85%** | Add tests per app incrementally |
| Views (thin) | **≥ 70%** | Often covered by API tests |
| Migrations, `populate_test_data` | Excluded | See `.coveragerc` |

---

## Frontend layout

```
fe/src/
├── utils/
│   ├── formValidation.js
│   ├── formValidation.test.js
│   ├── userFormPayload.js
│   ├── userFormPayload.test.js
│   ├── categoryTree.js
│   └── categoryTree.test.js
├── config/
│   ├── apiBaseUrl.js
│   └── apiBaseUrl.test.js
├── components/
│   └── …/*.test.js           # Component tests (RTL) — add sparingly
└── test-utils/               # Shared render/mocks (when needed)
```

### Principles

1. **Extract logic from components** into `src/utils/` (or hooks) and test there — keeps UI tests small.
2. **Co-locate** tests: `foo.js` + `foo.test.js` in the same folder.
3. **Do not** chase 95% on every React page; chase 95% on **utils, config, hooks**.

### Run

```bash
cd fe

# Watch mode
npm test

# CI / single run
npm test -- --watchAll=false

# Coverage (see package.json thresholds)
npm run test:coverage

# Logic-only slice
npm run test:unit
```

### Coverage targets (frontend)

| Path | Target |
|------|--------|
| `src/utils/**` | **≥ 95%** |
| `src/config/**` | **≥ 95%** |
| `src/hooks/**` | **≥ 85%** |
| `src/components/**` | Grow over time; not gated at 95% |

Jest enforces thresholds in `package.json` → `jest.coverageThreshold`.

---

## What to test when you change code

| Change | Add tests in |
|--------|----------------|
| New API endpoint | `be/<app>/tests/test_views.py` or `test_*_api.py` |
| Service method | `be/<app>/tests/test_services.py` |
| Serializer validation | `be/<app>/tests/test_*_serializer.py` |
| FE util / payload builder | `fe/src/utils/<name>.test.js` |
| Role / module flag | Existing `*Display.test.js`, `roleAccess.test.js` |

---

## CI checklist

```bash
# Backend
cd be && USE_SQLITE=true coverage run manage.py test && coverage report --fail-under=80

# Frontend
cd fe && npm run test:coverage
```

Adjust `--fail-under` as coverage improves.

---

## Related docs

- [POS_UX_ROLES_AND_TESTING.md](./POS_UX_ROLES_AND_TESTING.md) — personas, E2E
- [SETUP.md](./SETUP.md) — Docker test commands
