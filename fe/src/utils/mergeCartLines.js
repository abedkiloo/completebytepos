function cartLineKey(item) {
  return item?.variant_id ? `${item.id}-${item.variant_id}` : `${item.id}`;
}

/**
 * Merge cart rows that share the same product + variant key (sums quantity).
 */
export function mergeCartLines(cart = []) {
  const byKey = new Map();
  for (const item of cart) {
    const key = cartLineKey(item);
    const existing = byKey.get(key);
    if (existing) {
      byKey.set(key, {
        ...existing,
        quantity: (existing.quantity || 0) + (item.quantity || 0),
      });
    } else {
      byKey.set(key, { ...item });
    }
  }
  return [...byKey.values()];
}

/**
 * Merge holding API item payloads before save (product_id + variant_id).
 */
export function mergeHoldingItemPayloads(items = []) {
  const byKey = new Map();
  for (const item of items) {
    const productId = item.product_id;
    const variantId = item.variant_id || null;
    const key = variantId ? `${productId}-${variantId}` : `${productId}`;
    const qty = Math.max(0, parseInt(item.quantity, 10) || 0);
    if (qty <= 0) continue;
    const existing = byKey.get(key);
    if (existing) {
      existing.quantity += qty;
      if (item.unit_price != null) {
        existing.unit_price = item.unit_price;
      }
    } else {
      byKey.set(key, {
        product_id: productId,
        variant_id: variantId,
        quantity: qty,
        unit_price: item.unit_price,
      });
    }
  }
  return [...byKey.values()];
}
