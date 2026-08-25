import {
  filterVariantsForStockAlert,
  parseProductFiltersFromSearch,
  productFiltersToSearchParams,
  productHasLowStock,
  productHasOutOfStock,
  summaryFilterFromCard,
  variantEffectiveThreshold,
  variantIsLowStock,
  variantIsOutOfStock,
  variantStockTone,
} from './variantStockAlerts';

describe('variantStockAlerts', () => {
  const product = {
    track_stock: true,
    has_variants: true,
    low_stock_threshold: 10,
    stock_quantity: 110,
  };

  it('detects an out-of-stock variant while parent stock remains positive', () => {
    const variants = [
      { is_active: true, stock_quantity: 0 },
      { is_active: true, stock_quantity: 110 },
    ];
    expect(productHasOutOfStock({ ...product, has_out_of_stock: true, variants })).toBe(true);
    expect(productHasLowStock({ ...product, is_low_stock: false, variants })).toBe(false);
    expect(variantIsOutOfStock(variants[0])).toBe(true);
    expect(variantStockTone(variants[0], product)).toBe('destructive');
  });

  it('detects low stock on a variant row', () => {
    const variant = { is_active: true, stock_quantity: 4, low_stock_threshold: 10 };
    expect(variantIsLowStock(variant, product)).toBe(true);
    expect(variantStockTone(variant, product)).toBe('warning');
    expect(variantEffectiveThreshold(variant, product)).toBe(10);
  });

  it('maps summary cards to list filters and search params', () => {
    expect(summaryFilterFromCard('Out of stock')).toEqual({
      is_active: '',
      low_stock: false,
      out_of_stock: true,
    });
    const params = productFiltersToSearchParams({
      low_stock: false,
      out_of_stock: true,
      is_active: '',
    });
    expect(params.toString()).toBe('out_of_stock=true');
    expect(
      parseProductFiltersFromSearch(new URLSearchParams('out_of_stock=true'))
    ).toEqual({
      low_stock: false,
      out_of_stock: true,
      is_active: '',
    });
  });

  it('keeps only out-of-stock variants when that filter is on', () => {
    const variants = [
      { id: 1, is_active: true, stock_quantity: 0 },
      { id: 2, is_active: true, stock_quantity: 400 },
      { id: 3, is_active: true, stock_quantity: 419 },
    ];
    expect(
      filterVariantsForStockAlert(variants, product, { outOfStock: true }).map((v) => v.id)
    ).toEqual([1]);
  });

  it('keeps only low-stock variants when that filter is on', () => {
    const variants = [
      { id: 1, is_active: true, stock_quantity: 0 },
      { id: 2, is_active: true, stock_quantity: 4, low_stock_threshold: 10 },
      { id: 3, is_active: true, stock_quantity: 50 },
    ];
    expect(
      filterVariantsForStockAlert(variants, product, { lowStock: true }).map((v) => v.id)
    ).toEqual([2]);
  });
});
