import { normalizeProductForSale } from './moduleFeatures';
import { normalizeModuleSettings } from './moduleCache';
import { installLocalStorageMock } from '../test-utils';

function cacheVariantsDisabled() {
  localStorage.setItem(
    'enabled_modules',
    JSON.stringify(
      normalizeModuleSettings({
        products: {
          is_enabled: true,
          features: { product_variants: { is_enabled: false } },
        },
      })
    )
  );
}

describe('normalizeProductForSale stock', () => {
  beforeEach(() => {
    installLocalStorageMock();
    localStorage.clear();
    cacheVariantsDisabled();
  });

  it('keeps parent stock when variant rows sum to zero', () => {
    const out = normalizeProductForSale({
      id: 1,
      name: 'Variant',
      has_variants: true,
      stock_quantity: 400,
      price: 500,
      variants: [{ id: 10, stock_quantity: 0, is_active: true, price: 500 }],
    });
    expect(out.has_variants).toBe(false);
    expect(out.stock_quantity).toBe(400);
  });
});
