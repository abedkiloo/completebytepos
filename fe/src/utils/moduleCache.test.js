import {
  normalizeModuleSettings,
  isModuleEnabledInSettings,
  isFeatureEnabledInSettings,
} from './moduleCache';

describe('moduleCache', () => {
  test('normalizes legacy boolean module map', () => {
    const raw = { products: true, sales: false };
    const out = normalizeModuleSettings(raw);
    expect(out.products.is_enabled).toBe(true);
    expect(out.sales.is_enabled).toBe(false);
  });

  test('isModuleEnabled works on normalized booleans', () => {
    const modules = normalizeModuleSettings({ customers: true, invoicing: false });
    expect(isModuleEnabledInSettings(modules, 'customers')).toBe(true);
    expect(isModuleEnabledInSettings(modules, 'invoicing')).toBe(false);
  });

  test('isFeatureEnabled reads nested features', () => {
    const modules = normalizeModuleSettings({
      sales: {
        is_enabled: true,
        features: { pos: { is_enabled: true }, billing_pos: { is_enabled: false } },
      },
    });
    expect(isFeatureEnabledInSettings(modules, 'sales', 'pos')).toBe(true);
    expect(isFeatureEnabledInSettings(modules, 'sales', 'billing_pos')).toBe(false);
  });
});
