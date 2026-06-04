import { aggregateActiveVariantStock, catalogSellableStock } from './catalogStock';

describe('catalogSellableStock', () => {
  it('returns parent quantity when there are no variant rows', () => {
    expect(
      catalogSellableStock({
        has_variants: true,
        stock_quantity: 400,
        variants: [],
      })
    ).toBe(400);
  });

  it('uses max of parent and variant sum (regression: list showed 0, edit showed 400)', () => {
    expect(
      catalogSellableStock({
        has_variants: true,
        stock_quantity: 400,
        variants: [{ stock_quantity: 0, is_active: true }],
      })
    ).toBe(400);
  });

  it('uses variant sum when it exceeds parent', () => {
    expect(
      catalogSellableStock({
        has_variants: true,
        stock_quantity: 5,
        variants: [
          { stock_quantity: 3, is_active: true },
          { stock_quantity: 4, is_active: true },
        ],
      })
    ).toBe(7);
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
