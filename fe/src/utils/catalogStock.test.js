import { aggregateActiveVariantStock, catalogSellableStock } from './catalogStock';

describe('catalogSellableStock', () => {
  it('uses parent stock when variant rows are not embedded in the payload', () => {
    expect(
      catalogSellableStock({
        has_variants: true,
        stock_quantity: 400,
        variants: [],
      })
    ).toBe(400);
  });

  it('sums active variant rows (parent stock is not sold separately)', () => {
    expect(
      catalogSellableStock({
        has_variants: true,
        stock_quantity: 400,
        variants: [{ stock_quantity: 0, is_active: true }],
      })
    ).toBe(0);
    expect(
      catalogSellableStock({
        has_variants: true,
        stock_quantity: 5,
        variants: [
          { stock_quantity: 200, is_active: true },
          { stock_quantity: 40, is_active: true },
        ],
      })
    ).toBe(240);
  });

  it('returns parent stock when has_variants is false', () => {
    expect(
      catalogSellableStock({ has_variants: false, stock_quantity: 12, variants: [] })
    ).toBe(12);
  });

  it('ignores inactive variant rows in the sum', () => {
    expect(
      aggregateActiveVariantStock([
        { stock_quantity: 100, is_active: false },
        { stock_quantity: 2, is_active: true },
      ])
    ).toBe(2);
  });
});
