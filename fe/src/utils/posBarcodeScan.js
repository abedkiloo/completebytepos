/**
 * POS barcode scan helpers — shared by phone camera and Bluetooth HID guns.
 *
 * Mental model (least → most hardware):
 *   1. Normal phone browser — camera overlay decodes barcode → lookup → cart
 *   2. Same browser + Bluetooth HID gun — scanner "types" into the search box
 *   3. Native POS app — same APIs, richer camera / offline (later)
 *
 * HID guns need no special Bluetooth Web API: they emulate a keyboard and
 * work in ordinary HTTPS browsing as long as the search field is focused.
 */

/**
 * Normalize a raw scan / typed code for comparison.
 *
 * @param {unknown} value
 * @returns {string} Trimmed string, max 128 chars; empty when blank.
 */
export function normalizeScanCode(value) {
  if (value == null) return '';
  return String(value).trim().slice(0, 128);
}

/**
 * True when a product row is an exact SKU or barcode hit for the scan code.
 * Name-only matches are never treated as scan hits (avoids wrong auto-add).
 *
 * @param {object|null|undefined} product
 * @param {string} code
 * @returns {boolean}
 */
export function productMatchesScanCode(product, code) {
  const needle = normalizeScanCode(code).toLowerCase();
  if (!product || !needle) return false;
  const sku = normalizeScanCode(product.sku).toLowerCase();
  const barcode = normalizeScanCode(product.barcode).toLowerCase();
  return sku === needle || barcode === needle;
}

/**
 * Pick a single product for auto-add from search results.
 *
 * @param {Array<object>} results
 * @param {string} code
 * @returns {{ product: object|null, reason: 'exact'|'ambiguous'|'none'|'empty' }}
 */
export function pickExactScanProduct(results, code) {
  const list = Array.isArray(results) ? results : [];
  const needle = normalizeScanCode(code);
  if (!needle) return { product: null, reason: 'empty' };
  const exact = list.filter((row) => productMatchesScanCode(row, needle));
  if (exact.length === 1) return { product: exact[0], reason: 'exact' };
  if (exact.length > 1) return { product: null, reason: 'ambiguous' };
  // Backend may return a parent after a variant barcode hit — allow single
  // result when the query looks like a scan (digits / short code) and only
  // one row came back from exact-preferring search.
  if (list.length === 1 && looksLikeScanCode(needle)) {
    return { product: list[0], reason: 'exact' };
  }
  if (list.length === 0) return { product: null, reason: 'none' };
  return { product: null, reason: 'none' };
}

/**
 * Heuristic: codes that are mostly digits/dashes are scan-like (not a name).
 *
 * @param {string} code
 * @returns {boolean}
 */
export function looksLikeScanCode(code) {
  const raw = normalizeScanCode(code);
  if (raw.length < 3 || raw.length > 64) return false;
  return /^[0-9A-Za-z\-_.]+$/.test(raw) && /[0-9]/.test(raw);
}

/**
 * Debounce guard for identical successive scans (wave phone twice).
 *
 * @param {{ code: string, at: number }} last
 * @param {string} code
 * @param {number} [windowMs=450]
 * @returns {boolean} True when this scan should be ignored.
 */
export function isDuplicateScan(last, code, windowMs = 450) {
  const needle = normalizeScanCode(code);
  if (!needle || !last?.code) return false;
  const ms = Math.max(100, Math.min(2000, Number(windowMs) || 450));
  return (
    normalizeScanCode(last.code) === needle &&
    Date.now() - (last.at || 0) < ms
  );
}
