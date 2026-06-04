import { buildNavContext } from './navAccess';

describe('nav product_variants feature', () => {
  test('hides Sizes & colors when feature off in cache', () => {
    const ctx = buildNavContext(
      {
        products: {
          is_enabled: true,
          features: { product_variants: { is_enabled: false } },
        },
      },
      false
    );
    expect(ctx.isFeatureEnabled('products', 'product_variants')).toBe(false);
  });

  test('shows Sizes & colors when feature on', () => {
    const ctx = buildNavContext(
      {
        products: {
          is_enabled: true,
          features: { product_variants: { is_enabled: true } },
        },
      },
      false
    );
    expect(ctx.isFeatureEnabled('products', 'product_variants')).toBe(true);
  });

  test('registry default off when feature row missing', () => {
    const ctx = buildNavContext(
      {
        registry: { feature_defaults: { products: { product_variants: false } } },
        products: { is_enabled: true, features: {} },
      },
      false
    );
    expect(ctx.isFeatureEnabled('products', 'product_variants')).toBe(false);
  });
});
