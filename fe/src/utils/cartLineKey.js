/**
 * Stable keys for POS cart lines and holding/sale item payloads.
 * Single source — used by retail POS, billing POS, and line consolidation.
 */

export function saleLineKey(productId, variantId = null) {
  const vid = variantId || null;
  return vid ? `${productId}-${vid}` : `${productId}`;
}

/** Key for an in-memory cart row (`id` + optional `variant_id`). */
export function cartLineKey(item) {
  if (!item) return '';
  if (item.id != null) {
    return saleLineKey(item.id, item.variant_id);
  }
  if (item.product_id != null) {
    return saleLineKey(item.product_id, item.variant_id);
  }
  return '';
}

/** @deprecated Prefer `cartLineKey` — alias kept for existing POS imports. */
export const cartItemKey = cartLineKey;
