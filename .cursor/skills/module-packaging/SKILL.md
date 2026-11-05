---
name: module-packaging
description: >-
  CompleteBytePOS is sold as modules and packages. Use whenever adding or
  changing a feature, screen, API, export, or setting so it is package-
  configurable (ModuleSettings / ModuleFeature / ModuleSetting), gated in
  API + nav + mobile, and seeded for install presets.
---

# Module packaging (sellable modules & packages)

CompleteBytePOS is sold **by module and by package**. Every capability must be
turnable off for a tenant without rebuilding apps. Never ship a feature that is
always-on for every install.

## Layers (do not collapse them)

| Layer | What it is | Where |
|-------|------------|--------|
| **Module on/off** | SKU: whole product area | `ModuleSettings` + `module_registry.MODULE_DEFINITIONS` |
| **Catalog feature** | Sellable capability inside a module | `ModuleFeature` keys on that module in `module_registry.py` |
| **ModuleSetting** | Store tuning when the feature is installed | `module_settings_registry.py` + `*/module_settings.py` |
| **StoreSettings** | Store-wide prefs (payments, receipts, maker-checker) | `settings.models.StoreSettings` |
| **RBAC** | Who may use it | `accounts.Permission` — does **not** replace packaging |

**Rule:** ModuleFeature = *can this store buy/use it?*  
ModuleSetting = *how does this store run it once installed?*

## Mandatory checklist for every new capability

1. **Classify** — new module, new `ModuleFeature` under an existing module, or `ModuleSetting` only (UI/workflow). Prefer a **feature** for anything you might sell separately (export, priority, location filters, trading profit, late SMS).
2. **Register** in `be/settings/module_registry.py` (`_f(...)`). Add to relevant **PRESETS** (`retail_starter`, `retail_full`, `finance_pack`) so packages install correctly.
3. **Sync choices** — if you add a catalog **module**, update `ModuleSettings.MODULE_CHOICES` in `be/settings/models.py` (same names as the registry).
4. **Seed** — `init_modules` / feature rows use registry defaults; do not hardcode defaults only in the UI.
5. **Backend gate** — enforce on every relevant endpoint (not nav-only):
   - Module: `RequireModuleEnabled('…')`
   - Feature: `is_module_feature_enabled('module', 'key')` or `RequireModuleFeature`
   - Setting: helpers in `yourapp/module_settings.py` via `SettingsService`
6. **Frontend gate** — `NAV_SECTIONS` `module` + `feature: [module, key]`; hide controls with `isModuleFeatureEnabled` / `useModuleSettings`; route/report helpers must match API (e.g. `reportDisplay.js`).
7. **Mobile** — when the screen exists on Flutter, honour the same catalog feature (and typed settings where already loaded).
8. **Tests** — API returns 403 when feature/module off; FE unit/nav tests when present.
9. **Docs** — note the toggle in `docs/modules/<app>.md` when documenting that module.

## Anti-patterns (reject these)

- Feature only hidden in the nav but still callable via API.
- New Excel/PDF/SMS/filter/priority UI with **no** ModuleFeature or ModuleSetting.
- Adding a module to the registry but not `MODULE_CHOICES`.
- Treating RBAC permission as the package toggle.
- Duplicating feature lists only in `ModuleFeature.MODULE_FEATURES` without updating **`module_registry.py`** (registry is the source of truth for seeding).

## Recent package features (examples)

| Capability | Module | Feature key |
|------------|--------|-------------|
| Note/task priority | `daily_notes` | `note_priority` |
| Daily tasks | `daily_notes` | `daily_tasks` |
| Note checklists | `daily_notes` | `checklists` |
| Must-tick notes | `daily_notes` | `sticky_notes` |
| Sales history export | `sales` | `history_export` |
| Late sale SMS opt-in | `sales` | `late_sale_sms` |
| Phone camera barcode scan | `sales` | `camera_barcode_scan` |
| Kenya location filters | `customers` | `location_filters` |
| Trading profit & COGS | `reports` | `trading_profit` (+ `enable_financial_reports` ModuleSetting) |

## After registry changes

Remind operators/devs to run module seed so new feature rows appear:

```bash
python manage.py init_modules
```

(Or the project’s equivalent bootstrap.) Existing toggles must not be reset.

## Related docs

- `docs/modules/settings.md` — config hub overview
- `be/settings/module_registry.py` — catalog + presets
- `be/settings/module_settings_registry.py` — typed keys
- `be/settings/module_features.py` — `is_module_feature_enabled`
