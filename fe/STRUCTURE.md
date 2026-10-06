# Frontend structure & coding standards

Living guide for `CompleteBytePOS/fe`. Follow this when adding or changing React UI so POS, sales, and catalog screens stay consistent.

## What we are building

The **web admin / POS shell** for CompleteBytePOS: login, module-gated navigation, POS (retail + billing), products, customers/debt, sales history, daily sales, approvals, expenses, reports, audit log, settings.

Stack: **Create React App** (React 18), React Router, Axios (`src/services/api.js`), Tailwind + shared `ui/` primitives, Jest + Testing Library.

API base: `REACT_APP_API_URL` (Docker/nginx usually `/api`).

## Directory map

```
fe/src/
  App.js                 # routes (lazy pages)
  components/
    ui/                  # buttons, dialog, input, card, badge…
    page/                # PageShell, PageHeader, FilterBar, EmptyState…
    Shared/              # SearchableSelect, etc.
    POS/                 # v2 retail POS + billing/
    Sales/               # history, daily sales, sale dialogs
    Products/            # catalog forms
    Customers/           # dukas, debt, detail
    Approvals/, Expenses/, Reports/, AuditLog/, …
  hooks/                 # useModuleSettings, useListOrdering, …
  services/api.js        # all HTTP clients
  utils/                 # domain helpers (debt, recovery, formatters…)
  styles/                # compact forms, etc.
```

**Feature folders** own screens for one domain. Shared look-and-feel comes from `components/ui` and `components/page` — prefer those over one-off layouts.

## Page composition

List / filter screens should look like:

1. `PageShell`
2. `PageHeader` (title, short description, icon)
3. `FilterBar` + `FilterField` / `SearchField` / `SearchableSelect`
4. Content: table / cards / `EmptyState` / `PageLoading`
5. Pagination / `ListSortBar` as needed

**FilterBar:** keep `overflow-visible`. `SearchableSelect` menus render in a **portal** so they are not clipped or pushed into the filter row.

## Coding standards

### Components

- Function components only; hooks for state/effects.
- Colocate tests: `Foo.js` + `Foo.test.js` (or `Foo.bar.test.js` for focused suites).
- Keep POS state hooks (`usePOSState`, `useBillingPOSState`) free of JSX; pages compose UI.
- Dialogs: use `components/ui/dialog` (Radix). Always provide a title; use `description` prop when there is no visible description.

### API & errors

- All HTTP through `services/api.js` exports (`salesAPI`, `customersAPI`, …). Do not scatter raw axios instances.
- Surface errors with `formatApiError` / `toast` — user-facing sentences, not stack traces.
- After create/update that can 400 (duplicates, validation), show the server message (e.g. product already exists).

### Money & customers

- Treat wallet/debt display via shared helpers (`CustomerWalletBalance`, debt pages). Do not invent a second debt UI path.
- Customer search placeholders and filters must mention **duka, owner, contact, phone** — backend searches those fields; UI should not imply “duka name only”.
- Walk-in vs registered customer: use `utils/walkInCustomer` helpers.

### POS / billing

- Holding recovery (“Continue this sale?”) must run **once per session**, not on every customer search refresh (`holdingCheckedRef` / `recoveryResolvedRef` pattern in `useBillingPOSState`).
- After Continue, searching or adding a customer must **not** re-open recovery.
- Draft sync is debounced; use `skipNextSyncRef` when hydrating from a holding so restore does not immediately overwrite.

### Forms & confirms

- Destructive or money commits: confirm dialog with a short summary of what will be written (`formCommitSummary` / sale commit patterns).
- Product create with variants: multipart + `variant_combinations`; do not assume nested `variants[]` alone.

### Styling

- Prefer Tailwind utility classes and `cn()` from `lib/cn`.
- Reuse `ui/*` variants (button sizes for POS touch targets).
- Avoid new global CSS unless shared across modules; put feature CSS under `styles/` only when needed.
- Match existing visual language of the module you are editing — do not introduce a parallel design system.

## Routing & modules

- Routes live in `App.js` (lazy imports).
- Gate features with module settings / permissions (`FeatureFlag`, `useModuleSettings`, `utils/roleAccess`). Do not show admin-only screens to cashiers.
- Audit log and sensitive finance screens stay manager/admin.

## Testing

```bash
cd fe
npm test -- --watchAll=false --testPathPattern="CustomerPicker.search|useBillingPOSState.recovery"
```

- Mock `services/api` and heavy `ui/dialog` when testing pages.
- Cover recovery latch, customer search wiring, and money-confirm flows when you touch them.
- Prefer user-centric queries (`getByRole`, accessible names) over brittle CSS selectors. For portal menus, use `data-testid` (e.g. `searchable-select-menu`).

## Env & build

| File | Role |
|------|------|
| `.env.development` | Local CRA |
| `.env.production` | Production build (`REACT_APP_API_URL=/api` typical) |
| Root Compose `.env` / `.env.uat` | Injected at image build for Docker |

Do not hardcode `shop.omuwenga.com` or UAT hosts in components — use `REACT_APP_API_URL`.

The orange **ngrok configuration** overlay is a local/dev helper; on production HTTPS shops it is noise if API calls already hit the same origin `/api`. Do not “fix” prod by setting ngrok URLs.

## Do / don’t

| Do | Don’t |
|----|--------|
| Use `PageShell` + `FilterBar` + portal selects | Absolute dropdowns inside `overflow-x-hidden` parents |
| One-shot holding recovery | Re-fetch active holding on every customer list change |
| Search copy: duka / owner / contact / phone | Placeholder “name only” when API searches more |
| `api.js` + toast on failure | Ad-hoc fetch in a leaf component |
| Test recovery + search when changing POS customer UX | Ship POS changes with no hook test |
| Extend existing Sales/Products patterns | New parallel “v3” folder without need |
