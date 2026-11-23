/**
 * Product catalog field access (mirrors be/products/catalog_access.py).
 */
import { PERSONA } from './roleAccess';
import { isModuleFlagEnabled } from './moduleSettingsCache';
import {
  showProductCostPrice,
  showProductMrp,
  showProductStatus,
} from './productDisplay';

export function salesCatalogAccessEnabled(productSettings, storeSettings) {
  const moduleOn = isModuleFlagEnabled(productSettings, 'allow_sales_catalog_access', true);
  const storeOn = storeSettings?.allow_sales_add_products !== false;
  return moduleOn && storeOn;
}

export function salesMayEditCatalogDetails(settings) {
  return isModuleFlagEnabled(settings, 'allow_sales_edit_catalog_details', true);
}

export function salesMayEditPricing(settings) {
  return isModuleFlagEnabled(settings, 'allow_sales_edit_pricing', false);
}

export function salesMayEditCost(settings) {
  return isModuleFlagEnabled(settings, 'allow_sales_edit_cost', false);
}

export function salesMayEditStock(settings) {
  return isModuleFlagEnabled(settings, 'allow_sales_edit_stock', false);
}

export function managerMayEditPricing(settings) {
  return isModuleFlagEnabled(settings, 'allow_manager_edit_pricing', true);
}

export function managerMayEditCost(settings) {
  return isModuleFlagEnabled(settings, 'allow_manager_edit_cost', false);
}

/**
 * @returns {{ catalog: boolean, pricing: boolean, cost: boolean, stock: boolean, catalogOnly: boolean }}
 */
export function resolveProductFieldAccess(persona, productSettings = {}, storeSettings = {}) {
  if (persona === PERSONA.SUPER_ADMIN) {
    return {
      catalog: true,
      pricing: true,
      cost: true,
      stock: true,
      catalogOnly: false,
    };
  }

  if (persona === PERSONA.MANAGER) {
    const pricing = managerMayEditPricing(productSettings);
    const cost = managerMayEditCost(productSettings);
    return {
      catalog: true,
      pricing,
      cost,
      stock: true,
      catalogOnly: false,
    };
  }

  if (persona === PERSONA.SALES) {
    const catalogAccess = salesCatalogAccessEnabled(productSettings, storeSettings);
    const catalog = catalogAccess && salesMayEditCatalogDetails(productSettings);
    const pricing = catalogAccess && salesMayEditPricing(productSettings);
    const cost = catalogAccess && salesMayEditCost(productSettings);
    const stock = catalogAccess && salesMayEditStock(productSettings);
    return {
      catalog,
      pricing,
      cost,
      stock,
      catalogOnly: catalog && !pricing && !cost && !stock,
    };
  }

  return {
    catalog: false,
    pricing: false,
    cost: false,
    stock: false,
    catalogOnly: false,
  };
}

/**
 * Cost of goods is visible to an admin or super admin, or a role with the box checked.
 *
 * A missing login cache is false, so an empty session does not show cost.
 *
 * @returns {boolean} True when cost, margin, and stock value may be shown.
 */
export function userMaySeeProductCost() {
  let user = null;
  let profile = null;
  let permissions = [];
  try {
    user = JSON.parse(localStorage.getItem('user') || 'null');
    profile = JSON.parse(localStorage.getItem('profile') || 'null');
    permissions = JSON.parse(localStorage.getItem('permissions') || '[]');
  } catch (err) {
    return false;
  }
  if (user?.is_superuser || profile?.is_super_admin) return true;
  const role = String(profile?.role || '');
  if (role === 'admin' || role === 'super_admin') return true;
  const name = String(profile?.custom_role?.name || '');
  if (name === 'Super Admin' || name === 'Admin' || name === 'Administrator') return true;
  return (Array.isArray(permissions) ? permissions : []).some(
    (row) =>
      (row?.module === 'products' && row?.action === 'view_cost')
      || (row?.module === 'reports' && row?.action === 'profit')
  );
}

export function userMayEditAnyProductFinancialFieldFromStorage(
  persona,
  productSettings,
  storeSettings
) {
  const access = resolveProductFieldAccess(persona, productSettings, storeSettings);
  return access.pricing || access.cost || access.stock;
}

/**
 * Read-only product detail visibility (module flags × role field access).
 * @param {{ catalog: boolean, pricing: boolean, cost: boolean, stock: boolean, catalogOnly: boolean }} fieldAccess
 * @param {object} productModuleSettings
 * @param {object} [storeSettings]
 */
export function resolveProductDetailVisibility(
  fieldAccess,
  productModuleSettings = {},
  storeSettings = {}
) {
  const showStatus = showProductStatus(productModuleSettings, storeSettings);
  const showPricing = Boolean(fieldAccess?.pricing);
  const showCost = (
    Boolean(fieldAccess?.cost) || userMaySeeProductCost()
  ) && showProductCostPrice(productModuleSettings);
  const showMrp = showPricing && showProductMrp(productModuleSettings);
  const showStock = Boolean(fieldAccess?.stock);
  const showProfit = showPricing && showCost;
  const catalogOnly = Boolean(fieldAccess?.catalogOnly);

  return {
    showStatus,
    showPricing,
    showCost,
    showMrp,
    showStock,
    showProfit,
    catalogOnly,
    canViewCatalog: Boolean(fieldAccess?.catalog),
    canEdit: Boolean(fieldAccess?.catalog),
  };
}
