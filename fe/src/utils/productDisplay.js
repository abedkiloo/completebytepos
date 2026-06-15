/**
 * Shared display tokens and flags for the Products module.
 */
import { isModuleFlagEnabled } from './moduleSettingsCache';
import { isModuleFeatureEnabled } from './moduleFeatures';

export const SELLING_PRICE_CLASS = 'text-success font-medium tabular-nums';

/** Shown on parent rows for products that sell via variants (prices live on variant rows). */
export const VARIANT_PARENT_PRICE_MASK = '***';

export const STOCK_ON_HAND_LABEL = 'Stock on hand';
export const STOCK_OPENING_LABEL = 'Opening stock';
export const STOCK_COUNT_LABEL = 'Stock count';

/** Sets exact on-hand from the Products list (click stock on a product row). */
export const STOCK_COUNT_HINT =
  'Replaces the system quantity with what you counted. Use Stock → Stock adjustment only to add or remove units without a full count.';

export const STOCK_ADJUST_HINT =
  'Adds to or subtracts from on-hand stock. Example: 10 on hand and you enter +3 → 13. To set the correct count after a physical count, click the stock quantity on the product in Products.';

export const STOCK_OPENING_HINT =
  'Starting quantity when this product or variant is first saved.';

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
