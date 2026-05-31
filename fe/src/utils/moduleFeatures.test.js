import { getDefaultPosRoute, isBillingPosEnabled } from './moduleFeatures';
import { normalizeModuleSettings } from './moduleCache';

function cacheModules(raw) {
  localStorage.setItem('enabled_modules', JSON.stringify(normalizeModuleSettings(raw)));
}

describe('moduleFeatures POS routing', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test('getDefaultPosRoute uses terminal when billing_pos is enabled', () => {
    cacheModules({
      sales: {
        is_enabled: true,
        features: {
          pos: { is_enabled: true },
          billing_pos: { is_enabled: true },
        },
      },
    });
    expect(isBillingPosEnabled()).toBe(true);
    expect(getDefaultPosRoute()).toBe('/pos/billing');
  });

  test('getDefaultPosRoute falls back to retail POS when billing is off', () => {
    cacheModules({
      sales: {
        is_enabled: true,
        features: {
          pos: { is_enabled: true },
          billing_pos: { is_enabled: false },
        },
      },
    });
    expect(getDefaultPosRoute()).toBe('/pos');
  });
});
