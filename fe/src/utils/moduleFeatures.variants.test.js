import { isProductVariantsEnabled } from './moduleFeatures';
import { normalizeModuleSettings } from './moduleCache';

function cacheModules(raw) {
  localStorage.setItem('enabled_modules', JSON.stringify(normalizeModuleSettings(raw)));
}

describe('isProductVariantsEnabled system-wide', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test('uses registry default when cache empty (off until enabled)', () => {
    expect(isProductVariantsEnabled()).toBe(false);
  });

  test('reads DB-backed cache when feature is on', () => {
    cacheModules({
      products: {
        is_enabled: true,
        features: { product_variants: { is_enabled: true } },
      },
    });
    expect(isProductVariantsEnabled()).toBe(true);
  });

  test('uses API registry.feature_defaults when feature row missing', () => {
    cacheModules({
      registry: { feature_defaults: { products: { product_variants: false } } },
      products: { is_enabled: true, features: {} },
    });
    expect(isProductVariantsEnabled()).toBe(false);
  });

  test('nav and form stay aligned when toggle is on', () => {
    cacheModules({
      registry: { feature_defaults: { products: { product_variants: false } } },
      products: {
        is_enabled: true,
        features: { product_variants: { is_enabled: true } },
      },
    });
    expect(isProductVariantsEnabled()).toBe(true);
  });
});
