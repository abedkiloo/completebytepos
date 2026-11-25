import {
  holdingSaleItemToCartLine,
  resolveHoldingCatalogUnitPrice,
} from './billingCartLine';

describe('billingCartLine stress', () => {
  beforeEach(() => {
    localStorage.setItem(
      'enabled_modules',
      JSON.stringify({
        products: {
          is_enabled: true,
          features: { product_variants: { is_enabled: true } },
        },
      })
    );
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('resolves catalog floor for hundreds of marked-up holding lines', () => {
    for (let i = 0; i < 400; i += 1) {
      const unit = 1000 + (i % 50) * 100;
      const catalog = 200 + (i % 20);
      const item = {
        product_id: i + 1,
        product_name: `P-${i}`,
        quantity: 1 + (i % 5),
        unit_price: String(unit),
        product: {
          id: i + 1,
          name: `P-${i}`,
          price: String(catalog),
          selling_price: String(catalog),
          mrp: String(catalog),
          stock_quantity: 999,
        },
      };
      expect(resolveHoldingCatalogUnitPrice(item)).toBe(catalog);
      const line = holdingSaleItemToCartLine(item, { validateStock: false });
      expect(line.catalog_price).toBe(catalog);
      expect(line.price).toBe(unit);
      expect(line.selling_price).toBe(catalog);
    }
  });
});
