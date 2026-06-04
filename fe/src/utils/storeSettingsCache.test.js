import {
  DEFAULT_STORE_SETTINGS,
  cacheStoreSettings,
  readCachedStoreSettings,
  clearStoreSettingsCache,
} from './storeSettingsCache';

describe('storeSettingsCache', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test('readCachedStoreSettings returns defaults when empty', () => {
    expect(readCachedStoreSettings()).toEqual(DEFAULT_STORE_SETTINGS);
    expect(readCachedStoreSettings().maker_checker_enabled).toBe(true);
  });

  test('cacheStoreSettings merges and persists', () => {
    cacheStoreSettings({
      allow_sales_add_products: true,
      enabled_payment_methods: ['cash'],
      receipt_footer_text: 'Karibu',
    });
    const stored = readCachedStoreSettings();
    expect(stored.allow_sales_add_products).toBe(true);
    expect(stored.enabled_payment_methods).toEqual(['cash']);
    expect(stored.receipt_footer_text).toBe('Karibu');
    expect(stored.sales_catalog_skip_pricing).toBe(true);
  });

  test('readCachedStoreSettings recovers from corrupt JSON', () => {
    localStorage.setItem('store_settings', 'not-json');
    expect(readCachedStoreSettings()).toEqual(DEFAULT_STORE_SETTINGS);
  });

  test('cacheStoreSettings ignores falsy data', () => {
    cacheStoreSettings(null);
    expect(localStorage.getItem('store_settings')).toBeNull();
  });

  test('clearStoreSettingsCache removes stored values', () => {
    cacheStoreSettings({ receipt_auto_print: true });
    clearStoreSettingsCache();
    expect(readCachedStoreSettings()).toEqual(DEFAULT_STORE_SETTINGS);
  });
});
