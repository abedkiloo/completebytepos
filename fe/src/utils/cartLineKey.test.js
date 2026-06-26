import { cartLineKey, cartItemKey, saleLineKey } from './cartLineKey';

describe('cartLineKey', () => {
  it('saleLineKey distinguishes variant rows', () => {
    expect(saleLineKey(1, 10)).toBe('1-10');
    expect(saleLineKey(1, 11)).toBe('1-11');
    expect(saleLineKey(1)).toBe('1');
  });

  it('cartLineKey matches saleLineKey for cart rows', () => {
    expect(cartLineKey({ id: 1, variant_id: 10 })).toBe('1-10');
    expect(cartLineKey({ id: 1 })).toBe('1');
    expect(cartLineKey({ product_id: 5, variant_id: 12 })).toBe('5-12');
  });

  it('cartItemKey is an alias for cartLineKey', () => {
    const row = { id: 2, variant_id: 3 };
    expect(cartItemKey(row)).toBe(cartLineKey(row));
  });
});
