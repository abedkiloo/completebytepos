import { mergeCartLines, mergeHoldingItemPayloads } from './mergeCartLines';

describe('mergeCartLines', () => {
  it('merges rows with the same product and variant', () => {
    const merged = mergeCartLines([
      { id: 5, variant_id: 12, name: 'Zipper', quantity: 2, price: 100 },
      { id: 5, variant_id: 12, name: 'Zipper', quantity: 3, price: 100 },
    ]);
    expect(merged).toHaveLength(1);
    expect(merged[0].quantity).toBe(5);
  });

  it('keeps distinct variant rows separate', () => {
    const merged = mergeCartLines([
      { id: 5, variant_id: 12, quantity: 2, price: 100 },
      { id: 5, variant_id: 13, quantity: 1, price: 90 },
    ]);
    expect(merged).toHaveLength(2);
  });

  it('merges product-only rows when variant_id is absent', () => {
    const merged = mergeCartLines([
      { id: 7, quantity: 1, price: 50 },
      { id: 7, quantity: 2, price: 50 },
    ]);
    expect(merged).toHaveLength(1);
    expect(merged[0].quantity).toBe(3);
  });
});

describe('mergeHoldingItemPayloads', () => {
  it('sums duplicate holding lines', () => {
    const merged = mergeHoldingItemPayloads([
      { product_id: 5, variant_id: 12, quantity: 2, unit_price: 100 },
      { product_id: 5, variant_id: 12, quantity: 1, unit_price: 100 },
      { product_id: 5, variant_id: null, quantity: 4, unit_price: 50 },
    ]);
    expect(merged).toEqual([
      { product_id: 5, variant_id: 12, quantity: 3, unit_price: 100 },
      { product_id: 5, variant_id: null, quantity: 4, unit_price: 50 },
    ]);
  });
});
