import { catalogSellableStock } from './catalogStock';
import {
  normalizeModuleSettings,
  readCachedModules,
  isFeatureEnabledInSettings,
  registryFeatureDefault,
} from './moduleCache';
import { localRegistryFeatureDefault } from '../config/moduleFeatureDefaults';
import { withSellingPriceFields } from './productPricing';

/**
 * Read module feature flags cached by Layout after login / refresh.
 * Uses DB-backed cache plus registry defaults (same rules as the backend).
 */

function resolveRegistryDefault(moduleName, featureKey) {
  const settings = readCachedModules();
  const fromApi = registryFeatureDefault(settings, moduleName, featureKey);
  if (settings?.registry?.feature_defaults) {
    return fromApi;
  }
  return localRegistryFeatureDefault(moduleName, featureKey);
}

/**
 * @param {string} moduleName
 * @param {string} featureKey
 * @param {boolean} [explicitDefault] — only used when the feature row is absent from cache
 */
export function isModuleFeatureEnabled(moduleName, featureKey, explicitDefault) {
  const registryDefault = resolveRegistryDefault(moduleName, featureKey);
  const fallback =
    explicitDefault !== undefined ? explicitDefault : registryDefault;
  const settings = readCachedModules();
  if (!settings || Object.keys(settings).length === 0) {
    return fallback;
  }
  return isFeatureEnabledInSettings(settings, moduleName, featureKey, {
    defaultWhenMissing: fallback,
  });
}

/** Product size/color variants — registry default off until enabled in Module Settings. */
export function isProductVariantsEnabled() {
  return isModuleFeatureEnabled('products', 'product_variants');
}

/** Terminal POS (invoices, held carts) — off unless enabled in Module Settings. */
export function isBillingPosEnabled() {
  return isModuleFeatureEnabled('sales', 'billing_pos', false);
}

/** Retail POS (fast walk-in checkout). */
export function isRetailPosEnabled() {
  return isModuleFeatureEnabled('sales', 'pos', true);
}

/** Primary checkout route: Terminal POS when active, otherwise Retail POS. */
export function getDefaultPosRoute() {
  if (isBillingPosEnabled()) {
    return '/pos/billing';
  }
  if (isRetailPosEnabled()) {
    return '/pos';
  }
  return '/pos/billing';
}

/**
 * When variants are disabled at POS, sell the parent product using
 * sellable stock (max of parent and active variant rows) if the catalogue
 * was set up with variants.
 */
export function normalizeProductForSale(product) {
  if (!product) return product;
  if (isProductVariantsEnabled()) {
    return withSellingPriceFields(product);
  }
  const base = withSellingPriceFields(product);
  const normalized = {
    ...base,
    variant_id: null,
    has_variants: false,
    stock_quantity: catalogSellableStock(base),
  };
  if (product.has_variants && Array.isArray(product.variants) && product.variants.length) {
    const active = product.variants.filter((v) => v.is_active !== false);
    if (active.length) {
      if (!normalized.price) {
        const first = active.find((v) => v.price != null) || active[0];
        const selling = parseFloat(
          first.effective_price ?? first.selling_price ?? first.price ?? 0
        );
        normalized.price = selling;
        normalized.selling_price = selling;
      }
      if (!normalized.mrp) {
        const first = active[0];
        normalized.mrp = parseFloat(
          first.effective_mrp ?? first.mrp ?? normalized.selling_price
        );
      }
    }
  }
  return normalized;
}

/** @deprecated Use readCachedModules + normalizeModuleSettings from moduleCache */
export function getModuleSettingsFromCache() {
  return readCachedModules();
}
