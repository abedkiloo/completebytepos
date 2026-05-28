import { withSellingPriceFields } from './productPricing';

/**
 * Read module feature flags cached by Layout after login / refresh.
 * Defaults are conservative: unknown features are treated as disabled.
 */

import { normalizeModuleSettings } from './moduleCache';

export function isModuleFeatureEnabled(moduleName, featureKey, defaultValue = false) {
  try {
    const cached = normalizeModuleSettings(
      JSON.parse(localStorage.getItem('enabled_modules') || '{}')
    );
    const mod = cached[moduleName];
    if (!mod || mod.is_enabled === false) {
      return defaultValue;
    }
    const feat = mod.features?.[featureKey];
    if (feat == null) {
      return defaultValue;
    }
    return Boolean(feat.is_enabled);
  } catch {
    return defaultValue;
  }
}

/** Product size/color variants — off by default until enabled in Module Settings. */
export function isProductVariantsEnabled() {
  return isModuleFeatureEnabled('products', 'product_variants', false);
}

/**
 * When variants are disabled at POS, sell the parent product using
 * aggregated variant stock/price if the catalogue was set up with variants.
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
    stock_quantity: base.stock_quantity,
  };
  if (product.has_variants && Array.isArray(product.variants) && product.variants.length) {
    const active = product.variants.filter((v) => v.is_active !== false);
    if (active.length) {
      normalized.stock_quantity = active.reduce(
        (sum, v) => sum + (parseInt(v.stock_quantity, 10) || 0),
        0
      );
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
