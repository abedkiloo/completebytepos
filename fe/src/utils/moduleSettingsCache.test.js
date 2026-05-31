import {
  flattenModuleSettings,
  cacheModuleSettings,
  readCachedModuleSettings,
  isModuleFlagEnabled,
  clearModuleSettingsCache,
} from './moduleSettingsCache';

describe('moduleSettingsCache', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test('flattenModuleSettings extracts values', () => {
    const flat = flattenModuleSettings({
      module: 'products',
      settings: {
        show_status: { value: false, default_value: true, label: 'Status' },
      },
    });
    expect(flat.show_status).toBe(false);
  });

  test('cache and read roundtrip', () => {
    cacheModuleSettings('products', { show_status: true });
    expect(readCachedModuleSettings('products')).toEqual({ show_status: true });
    clearModuleSettingsCache('products');
    expect(readCachedModuleSettings('products')).toEqual({});
  });

  test('isModuleFlagEnabled treats undefined as default', () => {
    expect(isModuleFlagEnabled({}, 'show_status', true)).toBe(true);
    expect(isModuleFlagEnabled({ show_status: false }, 'show_status', true)).toBe(false);
  });
});
