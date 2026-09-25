/** Admin-editable storefront name shown in the header, receipts, and login. */

export const DEFAULT_STORE_NAME = 'Omuwenga Suppliers';

export function resolveStoreName(settings, fallbacks = []) {
  const fromSettings = String(settings?.store_name || '').trim();
  if (fromSettings) return fromSettings;
  for (const value of fallbacks) {
    const text = String(value || '').trim();
    if (text) return text;
  }
  return DEFAULT_STORE_NAME;
}
