import { getSellingPrice, getMrp, withSellingPriceFields } from './productPricing';

describe('productPricing', () => {
  it('getSellingPrice prefers selling_price then price', () => {
    expect(getSellingPrice({ selling_price: 99, price: 10 })).toBe(99);
    expect(getSellingPrice({ price: 10 })).toBe(10);
    expect(getSellingPrice(null)).toBe(0);
  });

  it('getMrp falls back to selling price', () => {
    expect(getMrp({ price: 50, mrp: 80 })).toBe(80);
    expect(getMrp({ price: 50 })).toBe(50);
  });

  it('withSellingPriceFields normalizes price fields', () => {
    const out = withSellingPriceFields({ price: 25, mrp: 30 });
    expect(out.price).toBe(25);
    expect(out.selling_price).toBe(25);
    expect(out.mrp).toBe(30);
  });

  it('handles non-numeric prices', () => {
    expect(getSellingPrice({ price: 'nope' })).toBe(0);
    expect(getMrp({ price: 10, mrp: 'bad' })).toBe(10);
    expect(withSellingPriceFields(null)).toBeNull();
  });
});
