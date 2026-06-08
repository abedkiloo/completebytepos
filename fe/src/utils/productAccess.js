/**
 * Product catalog field access (mirrors be/products/catalog_access.py).
 */
import { PERSONA } from './roleAccess';
import { isModuleFlagEnabled } from './moduleSettingsCache';

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

export function userMayEditAnyProductFinancialFieldFromStorage(
  persona,
  productSettings,
  storeSettings
) {
  const access = resolveProductFieldAccess(persona, productSettings, storeSettings);
  return access.pricing || access.cost || access.stock;
}
