# Backend structure & coding standards

Living guide for `CompleteBytePOS/be`. Follow this when adding or changing Django code so UAT/production stay consistent with how the POS is built today.

## What we are building

A multi-module retail POS API: products & stock, POS/billing sales, customers & debt, approvals (maker-checker), field agents, expenses, accounting journals, reports, and audit.

Stacks: **Django + DRF**, PostgreSQL in deploy, JWT auth, Docker entrypoint runs migrations then Gunicorn.

## App map

| App | Responsibility |
|-----|----------------|
| `config/` | Settings, root `urls.py`, exception handler, WSGI/ASGI |
| `accounts/` | Users, roles, permissions, **AuditLog** |
| `products/` | Catalog, variants, sizes/colors, stock helpers |
| `sales/` | Sales, holdings, customers, wallet/debt, daily sales, invoices |
| `inventory/` | Stock movements |
| `approvals/` | Pending changes, maker-checker |
| `agents/` | Field sites/orders; packing → field sale |
| `accounting/` | Journals / reversals |
| `expenses/`, `income/`, `bankaccounts/`, `transfers/` | Money in/out |
| `reports/` | Aggregated reporting APIs |
| `settings/` | Tenants, branches, module feature flags |
| `utils/` | Shared helpers (`audit`, tests base, etc.) |
| `services/` | Cross-app base services / datetime filters |

Domain URL prefix: `/api/<app>/…` (see `config/urls.py`).

## Layering (preferred shape)

Inside a Django app:

```
app/
  models.py          # persistence only — light helpers OK
  serializers.py     # request/response shape + field validation
  views.py           # thin: auth, parse request, call service, return Response
  services.py        # business rules, queries, side effects
  urls.py
  tests/
  management/commands/   # ops/repair only
  migrations/
```

**Rules**

1. **Views stay thin.** Do not put multi-step money/stock logic in `perform_create` without a service (or an explicit `transaction.atomic()` wrapping every side effect).
2. **Services own invariants.** Wallet debt, stock moves, journal posts, field-sale idempotency live in services (or focused modules like `sale_completion_approval.py`, `sale_debt_sync.py`, `field_sale.py`).
3. **Serializers validate input**, not post ledger entries.
4. Prefer **`django.core.exceptions.ValidationError`** in services → map to DRF 400 at the edge. Unhandled `IntegrityError` after a partial write is a bug — wrap creates in `transaction.atomic()`.

## Domain rules we must not break

### Sales & debt

- POS unpaid balance → customer wallet debt (`source_type='debt'`). Negative `wallet_balance` = customer owes us.
- **Return for correction** must reverse wallet effects **and** invalidate old debt/payment rows so re-complete can post the new unpaid amount (`reverse_sale_wallet_effects` + `_apply_sale_payment`).
- Field pack creates **one** sale (`record_field_sale`); idempotent on `order.sale_id`. Do not reintroduce a second FO-debt path alongside the sale debt.
- Repair stuck rows with `manage.py repair_sale_debt` (dry-run first), not ad-hoc SQL.

### Products & variants

- Create product + variants in **one** `transaction.atomic()`. Never leave an orphan product if variant sync fails.
- Variant SKUs must be collision-safe (similar color names like `GOLD` / `GOLD/ BLACK`). Use `build_variant_sku` / `allocate_unique_variant_sku`.
- Duplicate product **names** → 400 with a clear message; do not 500.

### Approvals

- Cashier sales that wait for manager stay `pending_approval` until approve; stock/wallet/journals post on approve (or immediate complete for privileged roles).
- Returned sales must be **edited** before resubmit (fingerprint / `assert_returned_sale_was_edited`).

### Audit

- Material writes go through `utils.audit.log_audit` / audited mixins. Store meaningful `changes` (diffs or entered payloads). List + detail APIs already expose them — keep payloads JSON-safe.

### Customers

- Search via `sales.customer_search.apply_customer_search`: **duka `name`**, **`owner_name`**, **`contact_person`**, code, email, phone (Kenya digit variants). Do not narrow search back to duka name only.

## Migrations

- **One leaf** per app. If two `0017_*` (or similar) appear, add an empty **merge** migration immediately.
- Never edit an already-applied migration on UAT/prod; add a new one.
- Keep `daily_notes/tests/test_migration_graph.py` (or equivalent) pointing at the current sales leaf.
- Local UAT `makemigrations` that creates a parallel leaf is a deploy blocker — merge before restart.

## Testing

- Prefer app tests under `app/tests/test_*.py`.
- Use `utils.tests.api_test_base` helpers (`SuperAdminAPITestCase`, role fixtures).
- Cover money paths with assertions on **wallet_balance**, debt txn `source_type`, and sale totals — not only HTTP 200.
- Run focused modules before broad suites:

```bash
cd be
python manage.py test sales.tests.test_customer_search products.tests.test_variant_combinations
```

- Management commands that mutate data need dry-run by default and a test.

## Coding style

- Python 3.12+, Django 5.x patterns already in tree.
- Explicit `Decimal` for money; never float for totals/debt.
- `select_related` / `prefetch_related` on list endpoints that join customer/product.
- Logging: `logger = logging.getLogger(__name__)`; audit failures must not break the user request.
- No secrets in repo; use `.env` / compose env files.

## Ops commands (examples)

```bash
# Inside backend container
python manage.py migrate
python manage.py repair_sale_debt --sale SALE-XXXX          # dry-run
python manage.py repair_sale_debt --sale SALE-XXXX --apply
python manage.py audit_unpaid_sales
```

## Do / don’t

| Do | Don’t |
|----|--------|
| Atomic create for product+variants | Commit product then sync variants outside the txn |
| Invalidate reversed debt rows on correction | Leave `source_type='debt'` rows that block re-apply |
| Merge migration leaves | Ship two `0017_*` sales leaves |
| Extend `apply_customer_search` for new identity fields | Filter only `name` in ad-hoc view code |
| Regression test for money/stock bugs | “Looks fine in admin” without wallet asserts |
