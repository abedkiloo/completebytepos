# CompleteByte POS — UX & product flow

Design goal: **fast, calm, predictable** — customers should feel the system “just works.”

## Mental model

```
Sign in → Dashboard (role-aware home)
       → Do work (POS / catalog / stock / reports)
       → Settings (admin only: users, modules, branches)
```

| Persona | Home focus | Sidebar |
|---------|------------|---------|
| **Sales** | Start sale, billing | Dashboard, POS, Billing, Customers |
| **Manager** | KPIs + stock alerts | Above + products, inventory, reports, finance |
| **Super Admin** | Full ops + config | Everything including module toggles |

Route guards (`roleAccess.js` + `navAccess.js`) redirect unauthorized URLs to `/`.

## Visual system

- Tokens: `fe/src/index.css` (indigo primary)
- Primitives: `fe/src/components/ui/`
- Page patterns: `fe/src/components/page/`

## Module settings (fresh install)

**Path:** Settings → Module settings (super admin only)

1. Backend stores `ModuleSettings` + `ModuleFeature` rows (`be/settings/models.py`).
2. `init_modules` command seeds defaults for new installs.
3. UI toggles call API → updates DB → refreshes `localStorage.enabled_modules` → fires `moduleSettingsUpdated` so Layout/nav react.

**Recommended first-time enable order:**

1. Products, Sales (POS + Billing), Customers  
2. Stock / Inventory, Reports  
3. Expenses, Income, Accounting (as needed)  
4. Settings → multi-branch (only if multiple locations)

Managers see toggles **read-only**; only super admin can change them.

## Rollout status

| Area | UI |
|------|-----|
| Dashboard, Login, Layout, Toast, Branch selector | Done |
| Products, Customers, Categories, Users | Done |
| Sales, Expenses, Income | Done |
| Inventory, Reports hub + detail shell | Done |
| Module settings | Done (redesign) |
| Suppliers, Roles, Accounting, Invoices, Barcodes, Normal sale | Legacy CSS — migrate with `page/` when touched |

## Performance

- `React.lazy` per route in `App.js`
- Skeleton loaders (`PageLoading`) on list pages
- `authAPI.me()` on app boot refreshes profile/permissions

## Adding a screen

```jsx
import { PageShell, PageHeader, PageLoading, EmptyState } from '../page';

export default function MyPage() {
  if (loading) return <Layout><PageLoading /></Layout>;
  return (
    <Layout>
      <PageShell>
        <PageHeader title="Title" description="One line.">
          <Button>Action</Button>
        </PageHeader>
        {/* content */}
      </PageShell>
    </Layout>
  );
}
```
