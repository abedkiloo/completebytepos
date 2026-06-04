/**
 * Inventory gates: ModuleSetting checkboxes AND catalog ModuleFeature flags.
 *
 * Accepts flat inventory checkbox map (from readCachedModuleSettings('inventory'))
 * or the full enabled_modules tree from getModuleSettings().
 */
import { isModuleFlagEnabled } from './moduleSettingsCache';
import { getModuleSettings, isFeatureEnabledInAny } from './moduleSettings';

function inventoryCheckboxFlags(settings) {
  if (!settings) return {};
  if (
    settings.enable_stock_adjustments !== undefined
    || settings.enable_stock_purchases !== undefined
    || settings.show_stock_movements !== undefined
  ) {
    return settings;
  }
  const nested = settings.inventory?.settings;
  if (!nested) return {};
  const flat = {};
  Object.entries(nested).forEach(([key, meta]) => {
    flat[key] = meta?.value ?? meta;
  });
  return flat;
}

function catalogModuleTree(settings) {
  if (settings?.inventory || settings?.stock) {
    return settings;
  }
  return getModuleSettings();
}

function catalogStockFeature(settings, featureKey) {
  return isFeatureEnabledInAny(
    ['inventory', 'stock'],
    featureKey,
    catalogModuleTree(settings),
  );
}

export function inventoryAdjustmentsAllowed(moduleSettings) {
  const flags = inventoryCheckboxFlags(moduleSettings);
  return (
    isModuleFlagEnabled(flags, 'enable_stock_adjustments', true) &&
    catalogStockFeature(moduleSettings, 'stock_adjustments')
  );
}

export function inventoryPurchasesAllowed(moduleSettings) {
  const flags = inventoryCheckboxFlags(moduleSettings);
  if (!isModuleFlagEnabled(flags, 'enable_stock_purchases', true)) {
    return false;
  }
  return (
    catalogStockFeature(moduleSettings, 'stock_adjustments') ||
    isFeatureEnabledInAny(['stock'], 'manage_stock', catalogModuleTree(moduleSettings))
  );
}

export function inventoryTransfersAllowed(moduleSettings) {
  const flags = inventoryCheckboxFlags(moduleSettings);
  return (
    isModuleFlagEnabled(flags, 'enable_stock_transfers', true) &&
    catalogStockFeature(moduleSettings, 'stock_transfers')
  );
}

export function inventoryMovementsAllowed(moduleSettings) {
  const flags = inventoryCheckboxFlags(moduleSettings);
  return (
    isModuleFlagEnabled(flags, 'show_stock_movements', true) &&
    catalogStockFeature(moduleSettings, 'stock_adjustments')
  );
}

export function inventoryLowStockAllowed(moduleSettings) {
  const flags = inventoryCheckboxFlags(moduleSettings);
  return (
    isModuleFlagEnabled(flags, 'show_low_stock_alerts', true) &&
    catalogStockFeature(moduleSettings, 'low_stock_alerts')
  );
}

export function inventoryReportAllowed(moduleSettings) {
  const flags = inventoryCheckboxFlags(moduleSettings);
  return (
    isModuleFlagEnabled(flags, 'enable_inventory_report', true) &&
    catalogStockFeature(moduleSettings, 'inventory_reports')
  );
}
