import { getSellableStock, isProductOutOfStock } from './productStock';

jest.mock('./moduleFeatures', () => ({
  normalizeProductForSale: (p) => p,
}));

describe('productStock', () => {
  it('returns zero when product is missing', () => {
    expect(getSellableStock(null)).toBe(0);
  });

  it('returns null when stock is not tracked', () => {
    expect(getSellableStock({ track_stock: false, stock_quantity: 0 })).toBeNull();
    expect(isProductOutOfStock({ track_stock: false, stock_quantity: 0 })).toBe(false);
  });

  it('parses stock quantity', () => {
    expect(getSellableStock({ track_stock: true, stock_quantity: '5' })).toBe(5);
    expect(getSellableStock({ track_stock: true, stock_quantity: '' })).toBe(0);
  });

  it('isProductOutOfStock when quantity is zero', () => {
    expect(isProductOutOfStock({ track_stock: true, stock_quantity: 0 })).toBe(true);
    expect(isProductOutOfStock({ track_stock: true, stock_quantity: 3 })).toBe(false);
  });
});
