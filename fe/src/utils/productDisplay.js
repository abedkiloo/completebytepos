/**
 * Shared display tokens and flags for the Products module.
 */
import { isModuleFlagEnabled } from './moduleSettingsCache';
import { isModuleFeatureEnabled } from './moduleFeatures';

export const SELLING_PRICE_CLASS = 'text-success font-medium tabular-nums';

export function showProductStatus(productModuleSettings, storeSettings) {
  if (storeSettings?.hide_entity_status_toggles) return false;
  return isModuleFlagEnabled(productModuleSettings, 'show_status', true);
}

export function showProductCostPrice(settings) {
  return isModuleFlagEnabled(settings, 'show_cost_price', true);
}

export function showProductMrp(settings) {
  return isModuleFlagEnabled(settings, 'show_mrp', true);
}

export function showProductSkuInList(settings) {
  return isModuleFlagEnabled(settings, 'show_sku_in_list', false);
}

export function showProductLowStockBadges(settings) {
  return isModuleFlagEnabled(settings, 'show_low_stock_badges', true);
}

export function productBulkOperationsEnabled(settings) {
  return isModuleFlagEnabled(settings, 'enable_bulk_operations', true);
}

export function productCsvImportExportEnabled(settings) {
  return isModuleFlagEnabled(settings, 'enable_csv_import_export', true);
}

/** Product images — install-level capability (Module Settings → features). */
export function productImagesEnabled() {
  return isModuleFeatureEnabled('products', 'product_images', false);
}
