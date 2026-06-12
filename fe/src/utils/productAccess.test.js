import { PERSONA } from './roleAccess';
import {
  resolveProductFieldAccess,
  resolveProductDetailVisibility,
  salesCatalogAccessEnabled,
  managerMayEditCost,
  managerMayEditPricing,
  salesMayEditCatalogDetails,
  salesMayEditCost,
  salesMayEditPricing,
  salesMayEditStock,
  userMayEditAnyProductFinancialFieldFromStorage,
} from './productAccess';

describe('productAccess', () => {
  const store = { allow_sales_add_products: true };

  test('defaults apply when settings omitted', () => {
    expect(resolveProductFieldAccess(PERSONA.MANAGER)).toMatchObject({
      catalog: true,
      pricing: true,
      stock: true,
    });
    expect(resolveProductFieldAccess(PERSONA.SALES)).toMatchObject({
      catalog: true,
      catalogOnly: true,
    });
  });

  test('super admin has full access', () => {
    expect(resolveProductFieldAccess(PERSONA.SUPER_ADMIN, {}, store)).toEqual({
      catalog: true,
      pricing: true,
      cost: true,
      stock: true,
      catalogOnly: false,
    });
  });

  test('manager pricing on, cost off by default', () => {
    const access = resolveProductFieldAccess(PERSONA.MANAGER, {}, store);
    expect(access.pricing).toBe(true);
    expect(access.cost).toBe(false);
    expect(access.stock).toBe(true);
  });

  test('manager can edit cost when setting enabled', () => {
    expect(managerMayEditCost({ allow_manager_edit_cost: true })).toBe(true);
  });

  test('sales catalog-only when transactional flags off', () => {
    const access = resolveProductFieldAccess(
      PERSONA.SALES,
      {
        allow_sales_catalog_access: true,
        allow_sales_edit_catalog_details: true,
        allow_sales_edit_pricing: false,
        allow_sales_edit_cost: false,
        allow_sales_edit_stock: false,
      },
      store
    );
    expect(access.catalogOnly).toBe(true);
    expect(access.pricing).toBe(false);
  });

  test('sales may edit pricing when flag on', () => {
    expect(
      resolveProductFieldAccess(
        PERSONA.SALES,
        { allow_sales_edit_pricing: true },
        store
      ).pricing
    ).toBe(true);
    expect(salesMayEditPricing({ allow_sales_edit_pricing: true })).toBe(true);
  });

  test('sales catalog blocked when module access off', () => {
    expect(
      salesCatalogAccessEnabled({ allow_sales_catalog_access: false }, store)
    ).toBe(false);
    expect(
      resolveProductFieldAccess(
        PERSONA.SALES,
        { allow_sales_catalog_access: false },
        store
      ).catalog
    ).toBe(false);
  });

  test('sales catalog blocked when store disallows add products', () => {
    expect(
      salesCatalogAccessEnabled({}, { allow_sales_add_products: false })
    ).toBe(false);
  });

  test('sales catalog details flag', () => {
    expect(salesMayEditCatalogDetails({ allow_sales_edit_catalog_details: false })).toBe(
      false
    );
    const access = resolveProductFieldAccess(
      PERSONA.SALES,
      { allow_sales_edit_catalog_details: false },
      store
    );
    expect(access.catalog).toBe(false);
  });

  test('sales may edit cost and stock when flags on', () => {
    expect(salesMayEditCost({ allow_sales_edit_cost: true })).toBe(true);
    expect(salesMayEditStock({ allow_sales_edit_stock: true })).toBe(true);
    const access = resolveProductFieldAccess(
      PERSONA.SALES,
      {
        allow_sales_edit_cost: true,
        allow_sales_edit_stock: true,
      },
      store
    );
    expect(access.cost).toBe(true);
    expect(access.stock).toBe(true);
    expect(access.catalogOnly).toBe(false);
  });

  test('manager pricing off when setting disabled', () => {
    expect(managerMayEditPricing({ allow_manager_edit_pricing: false })).toBe(false);
    expect(
      resolveProductFieldAccess(PERSONA.MANAGER, { allow_manager_edit_pricing: false }, store)
        .pricing
    ).toBe(false);
  });

  test('unknown persona has no access', () => {
    expect(resolveProductFieldAccess('guest', {}, store).catalog).toBe(false);
  });

  test('userMayEditAnyProductFinancialFieldFromStorage', () => {
    expect(
      userMayEditAnyProductFinancialFieldFromStorage(PERSONA.SALES, {}, store)
    ).toBe(false);
    expect(
      userMayEditAnyProductFinancialFieldFromStorage(
        PERSONA.SALES,
        { allow_sales_edit_stock: true },
        store
      )
    ).toBe(true);
    expect(
      userMayEditAnyProductFinancialFieldFromStorage(PERSONA.MANAGER, {}, store)
    ).toBe(true);
  });

  test('resolveProductDetailVisibility hides cost for manager by default', () => {
    const access = resolveProductFieldAccess(PERSONA.MANAGER, {}, store);
    const vis = resolveProductDetailVisibility(access, { show_cost_price: true }, store);
    expect(vis.showPricing).toBe(true);
    expect(vis.showCost).toBe(false);
    expect(vis.showStock).toBe(true);
  });

  test('resolveProductDetailVisibility shows full financials for super admin', () => {
    const access = resolveProductFieldAccess(PERSONA.SUPER_ADMIN, {}, store);
    const vis = resolveProductDetailVisibility(access, {}, store);
    expect(vis.showPricing).toBe(true);
    expect(vis.showCost).toBe(true);
    expect(vis.showStock).toBe(true);
    expect(vis.showProfit).toBe(true);
    expect(vis.canEdit).toBe(true);
  });

  test('resolveProductDetailVisibility respects module cost flag', () => {
    const access = resolveProductFieldAccess(PERSONA.SUPER_ADMIN, {}, store);
    const vis = resolveProductDetailVisibility(
      access,
      { show_cost_price: false },
      store
    );
    expect(vis.showCost).toBe(false);
    expect(vis.showProfit).toBe(false);
  });

  test('resolveProductDetailVisibility catalog-only sales see price not cost', () => {
    const access = resolveProductFieldAccess(
      PERSONA.SALES,
      {
        allow_sales_catalog_access: true,
        allow_sales_edit_catalog_details: true,
      },
      store
    );
    const vis = resolveProductDetailVisibility(access, {}, store);
    expect(vis.catalogOnly).toBe(true);
    expect(vis.showPricing).toBe(false);
    expect(vis.showCost).toBe(false);
    expect(vis.showStock).toBe(false);
  });
});
