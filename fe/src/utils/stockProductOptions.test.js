import {
  STOCK_PRODUCT_PAGE_SIZE,
  fetchTrackedStockProducts,
  formatStockProductOptionLabel,
  formatVariantStockOptionLabel,
  findProductById,
  toStockProductSelectOptions,
} from './stockProductOptions';
import { productsAPI } from '../services/api';

jest.mock('../services/api', () => ({
  productsAPI: { list: jest.fn() },
}));

describe('stockProductOptions', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

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

  test('toStockProductSelectOptions maps labels', () => {
    expect(
      toStockProductSelectOptions([
        { id: 1, name: 'A', stock_quantity: 2, has_variants: false },
      ])
    ).toEqual([
      { id: 1, name: 'A — stock 2', has_variants: false },
    ]);
  });

  test('formatVariantStockOptionLabel includes size color stock', () => {
    expect(
      formatVariantStockOptionLabel({
        id: 9,
        sku: 'SKU-1',
        size_name: 'L',
        color_name: 'Black',
        stock_quantity: 0,
      })
    ).toBe('SKU-1 · L · Black — stock 0');
  });

  test('fetchTrackedStockProducts uses page size cap and optional search', async () => {
    productsAPI.list.mockResolvedValue({
      data: { results: [{ id: 1, name: 'Hook' }] },
    });
    const rows = await fetchTrackedStockProducts({ search: 'hook' });
    expect(productsAPI.list).toHaveBeenCalledWith({
      track_stock: 'true',
      is_active: 'true',
      page_size: STOCK_PRODUCT_PAGE_SIZE,
      search: 'hook',
    });
    expect(rows).toEqual([{ id: 1, name: 'Hook' }]);
  });
});
