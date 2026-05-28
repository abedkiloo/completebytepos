import { normalizeProductForSale } from './moduleFeatures';

/**
 * Effective on-hand quantity for POS (respects variant aggregation when variants are off).
 * Returns null when the product does not track stock.
 */
export function getSellableStock(product) {
  if (!product) return 0;
  const p = normalizeProductForSale(product);
  if (p.track_stock === false) return null;
  const raw = p.stock_quantity;
  if (raw === undefined || raw === null || raw === '') return 0;
  const n = parseInt(raw, 10);
  return Number.isFinite(n) ? n : 0;
}

/** True when stock-tracked and quantity is zero or less. */
export function isProductOutOfStock(product) {
  const stock = getSellableStock(product);
  if (stock === null) return false;
  return stock <= 0;
}
