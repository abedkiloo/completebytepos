/** Cached tenant store settings (receipt, payments, catalog rules). */

const STORAGE_KEY = 'store_settings';

export const DEFAULT_STORE_SETTINGS = {
  allow_sales_add_products: true,
  sales_catalog_skip_pricing: true,
  hide_entity_status_toggles: false,
  enabled_payment_methods: ['cash', 'mpesa', 'wallet', 'card'],
  receipt_logo_url: null,
  receipt_header_text: '',
  receipt_footer_text: 'Thank you for your business!',
  receipt_show_logo: true,
  receipt_show_sku: false,
  receipt_auto_print: false,
  maker_checker_enabled: false,
  maker_checker_sales_controls: false,
  emergency_stock_mode: false,
};

export function cacheStoreSettings(data) {
  if (!data) return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...DEFAULT_STORE_SETTINGS, ...data }));
}

export function readCachedStoreSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_STORE_SETTINGS };
    return { ...DEFAULT_STORE_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_STORE_SETTINGS };
  }
}

export function clearStoreSettingsCache() {
  localStorage.removeItem(STORAGE_KEY);
}
