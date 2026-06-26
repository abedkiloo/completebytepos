import { cartLineKey, saleLineKey } from './cartLineKey';

function mergeRowsByKey(rows, keyFn, createRow, mergeInto) {
  const byKey = new Map();
  for (const row of rows) {
    const key = keyFn(row);
    if (!key) continue;
    const existing = byKey.get(key);
    if (existing) {
      mergeInto(existing, row);
    } else {
      byKey.set(key, createRow(row));
    }
  }
  return [...byKey.values()];
}

/**
 * Merge cart rows that share the same product + variant key (sums quantity).
 */
export function mergeCartLines(cart = []) {
  return mergeRowsByKey(
    cart,
    cartLineKey,
    (item) => ({ ...item }),
    (existing, item) => {
      existing.quantity = (existing.quantity || 0) + (item.quantity || 0);
    }
  );
}

/**
 * Merge holding API item payloads before save (product_id + variant_id).
 */
export function mergeHoldingItemPayloads(items = []) {
  return mergeRowsByKey(
    items,
    (item) => saleLineKey(item.product_id, item.variant_id || null),
    (item) => {
      const qty = Math.max(0, parseInt(item.quantity, 10) || 0);
      return {
        product_id: item.product_id,
        variant_id: item.variant_id || null,
        quantity: qty,
        unit_price: item.unit_price,
      };
    },
    (existing, item) => {
      const qty = Math.max(0, parseInt(item.quantity, 10) || 0);
      existing.quantity += qty;
      if (item.unit_price != null) {
        existing.unit_price = item.unit_price;
      }
    }
  ).filter((row) => row.quantity > 0);
}

/**
 * Cart → consolidated holding save payload (merge cart rows, then API shape).
 */
export function buildHoldingItemsFromCart(cart = []) {
  return mergeHoldingItemPayloads(
    mergeCartLines(cart).map((item) => ({
      product_id: item.id,
      variant_id: item.variant_id || null,
      quantity: item.quantity,
      unit_price: parseFloat(item.price),
    }))
  );
}
