/** Admin-editable storefront name shown in the header, receipts, and login. */

export const DEFAULT_STORE_NAME = 'Omuwenga Suppliers';
export const DEFAULT_STORE_TAGLINE = 'Think Furniture, Think Omuwenga';
export const DEFAULT_CONTACT_PHONE = '0718515142';
export const DEFAULT_BRAND_LOGO = '/logo.jpg';

export function resolveStoreName(settings, fallbacks = []) {
  const fromSettings = String(settings?.store_name || '').trim();
  if (fromSettings) return fromSettings;
  for (const value of fallbacks) {
    const text = String(value || '').trim();
    if (text) return text;
  }
  return DEFAULT_STORE_NAME;
}

export function resolveStoreLogoUrl(settings) {
  const uploaded = String(settings?.receipt_logo_url || '').trim();
  return uploaded || DEFAULT_BRAND_LOGO;
}

export function resolveReceiptLogoUrl(settings) {
  if (settings?.receipt_show_logo === false) return null;
  return resolveStoreLogoUrl(settings);
}

/** Resolves to `url` when it loads, otherwise to the packaged brand logo. */
export function loadableLogoUrl(url, { timeoutMs = 4000 } = {}) {
  if (!url || url === DEFAULT_BRAND_LOGO || typeof Image === 'undefined') {
    return Promise.resolve(url || null);
  }
  return new Promise((resolve) => {
    const img = new Image();
    const timer = setTimeout(() => resolve(DEFAULT_BRAND_LOGO), timeoutMs);
    img.onload = () => {
      clearTimeout(timer);
      resolve(url);
    };
    img.onerror = () => {
      clearTimeout(timer);
      resolve(DEFAULT_BRAND_LOGO);
    };
    img.src = url;
  });
}
