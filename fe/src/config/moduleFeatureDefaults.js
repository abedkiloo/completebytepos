/**
 * Fallback when ``registry.feature_defaults`` is not in enabled_modules yet.
 * Keep in sync with be/settings/module_registry.py (_f(..., enabled=False)).
 */
const EXPLICIT_FALSE = {
  sales: { normal_sale: false },
  customers: { customer_reports: false },
  invoicing: { invoice_reports: false },
  products: {
    qr_printing: false,
    product_variants: false,
    product_images: false,
  },
  suppliers: {
    supplier_products: false,
    supplier_reports: false,
  },
  inventory: { reorder_points: false },
  employees: { employee_reports: false },
  settings: { multi_branch_support: false },
};

export function localRegistryFeatureDefault(moduleName, featureKey) {
  if (EXPLICIT_FALSE[moduleName]?.[featureKey] === false) return false;
  return true;
}
