import {
  SELLING_PRICE_CLASS,
  showProductStatus,
  showProductCostPrice,
  showProductMrp,
  showProductSkuInList,
  productBulkOperationsEnabled,
  productCsvImportExportEnabled,
  STOCK_ADJUST_HINT,
  STOCK_COUNT_HINT,
} from './productDisplay';

describe('productDisplay', () => {
  test('SELLING_PRICE_CLASS uses success token', () => {
    expect(SELLING_PRICE_CLASS).toContain('text-success');
  });

  test('showProductStatus uses module settings show_status', () => {
    expect(showProductStatus({ show_status: true }, {})).toBe(true);
    expect(showProductStatus({ show_status: false }, {})).toBe(false);
  });

  test('showProductStatus returns false when hide_entity_status_toggles on', () => {
    expect(
      showProductStatus({ show_status: true }, { hide_entity_status_toggles: true })
    ).toBe(false);
  });

  test('display and workflow flags default sensibly', () => {
    expect(showProductCostPrice({})).toBe(true);
    expect(showProductMrp({})).toBe(true);
    expect(showProductSkuInList({})).toBe(false);
    expect(productBulkOperationsEnabled({})).toBe(true);
    expect(productCsvImportExportEnabled({})).toBe(true);
  });

  test('flags respect explicit false', () => {
    const off = {
      show_cost_price: false,
      show_mrp: false,
      enable_bulk_operations: false,
    };
    expect(showProductCostPrice(off)).toBe(false);
    expect(showProductMrp(off)).toBe(false);
    expect(productBulkOperationsEnabled(off)).toBe(false);
  });

  test('STOCK_COUNT_HINT describes set-count from Products', () => {
    expect(STOCK_COUNT_HINT).toMatch(/replaces the system quantity/i);
    expect(STOCK_COUNT_HINT).toContain('Stock adjustment');
  });

  test('STOCK_ADJUST_HINT points to Products for physical counts', () => {
    expect(STOCK_ADJUST_HINT).toMatch(/adds to or subtracts/i);
    expect(STOCK_ADJUST_HINT).toContain('Products');
  });
});
