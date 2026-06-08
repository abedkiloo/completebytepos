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

## Demo catalog (3 products)

| SKU | Product | Purpose |
|-----|---------|---------|
| DEMO-WATER-500 | Bottled Water 500ml | Low-ticket, high qty |
| DEMO-BREAD-WHT | Bread Loaf White | Per-piece retail |
| DEMO-OIL-1L | Cooking Oil 1L | Higher value item |

Replace these via **Products** once you know your real assortment.

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

| Phase | Apps | Focus | Status |
|-------|------|--------|--------|
| 1 | `sales`, `products` | Views + services edge cases (holding, stock, wallet) | Done |
| 2 | `inventory`, `reports` | Stock movements, transfer/undo, dashboard API, period filters | **Done** — see test packages below |
| 3 | `expenses`, `income`, `transfers` + persona flows | Service + API tests; three-user E2E | **Done** — `utils/tests/test_three_user_personas.py` |
| 3 | `expenses`, `income`, `accounting`, `transfers` | CRUD + permissions |
| 4 | `settings`, `accounts` | Module flags, bootstrap commands |

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
