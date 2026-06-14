import {
  formatStockProductOptionLabel,
  findProductById,
} from './stockProductOptions';

describe('stockProductOptions', () => {
  test('labels simple products with stock', () => {
    expect(
      formatStockProductOptionLabel({ name: 'Widget', sku: 'W-1', stock_quantity: 12 })
    ).toBe('Widget (W-1) — stock 12');
  });

  test('labels variant products with total stock', () => {
    expect(
      formatStockProductOptionLabel({
        name: 'T-Shirt',
        has_variants: true,
        stock_quantity: 45,
      })
    ).toBe('T-Shirt — variants, total stock 45');
  });

  test('findProductById matches numeric ids', () => {
    const products = [{ id: 3, name: 'A' }, { id: 7, name: 'B' }];
    expect(findProductById(products, '7')?.name).toBe('B');
    expect(findProductById(products, 99)).toBeNull();
  });

  test('formatStockProductOptionLabel handles null and missing sku', () => {
    expect(formatStockProductOptionLabel(null)).toBe('');
    expect(formatStockProductOptionLabel({ name: 'Widget', stock_quantity: null })).toBe(
      'Widget — stock 0'
    );
    expect(findProductById(null, 1)).toBeNull();
    expect(findProductById([], '')).toBeNull();
  });
});
