/** Default rows per page for paginated list screens (products, sales, expenses, etc.). */
export const DEFAULT_PAGE_SIZE = 10;

/**
 * POS / pickers catalog page size.
 * Must stay ≤ API ``API_MAX_PAGE_SIZE`` (default 200). Larger values were
 * silently capped and still forced heavy payloads on every POS open.
 */
export const CATALOG_FETCH_PAGE_SIZE = 200;
