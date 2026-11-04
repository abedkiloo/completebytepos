# settings

## Purpose

System configuration hub: module on/off, granular features, typed per-module JSON knobs, singleton store prefs, tenants/branches, install bootstrap.

## Key models

| Model | Role |
|-------|------|
| `ModuleSettings` / `ModuleFeature` | Module enable + feature toggles |
| `ModuleSetting` | Typed JSON value per `(module, key)` |
| `StoreSettings` | Singleton `pk=1` store prefs (payments, receipt, maker-checker) |
| `Tenant` / `Branch` | Company / outlet |

## Public APIs

Prefix: `/api/settings/` — modules, module-features, tenants, branches, store-settings, per-module keys, setup-status, fresh-install.

## Bounds & invariants

- Missing module/feature config defaults **enabled**.
- `StoreSettings` forced to `pk=1`.
- At most one HQ branch per tenant.
- Maker-checker may turn sensitive PATCHes into `PendingChange` (202).

## Audit

Features/tenants/branches use audited mixin; module toggle/preset/store patches use `log_domain_event`.

## Gaps

- Dual config systems (`ModuleSettings` vs `ModuleSetting`) can drift.
- `fresh-install` / `setup-status` are unauthenticated — ops exposure risk.
