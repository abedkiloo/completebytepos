import { saleLineKey } from './cartLineKey';
import { saleItemRefundableQuantity } from './saleItemDisplay';

/** Group sale lines by product + variant (duplicate-key). */
export function groupSaleItemsByLineKey(items = []) {
  const groups = new Map();
  for (const item of items) {
    const productId = item.product_id ?? item.product?.id;
    const variantId = item.variant_id ?? item.variant ?? null;
    const key = saleLineKey(productId, variantId);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }
  return groups;
}

/** Groups where the same product+variant appears on more than one sale line. */
export function detectDuplicateSaleLineGroups(items = []) {
  const duplicates = [];
  for (const [key, lines] of groupSaleItemsByLineKey(items)) {
    if (lines.length > 1) {
      duplicates.push({ key, lines });
    }
  }
  return duplicates;
}

export function hasDuplicateSaleLines(items = []) {
  return detectDuplicateSaleLineGroups(items).length > 0;
}

/** Sale item ids for duplicate rows after the first in each group. */
export function duplicateExcessSaleItemIds(items = []) {
  const ids = [];
  for (const { lines } of detectDuplicateSaleLineGroups(items)) {
    for (let i = 1; i < lines.length; i += 1) {
      ids.push(lines[i].id);
    }
  }
  return ids;
}

/**
 * Partial-refund qty map that refunds only excess duplicate lines
 * (keeps the first line per product+variant group).
 */
export function buildDuplicateRefundQtyMap(items = []) {
  const excessIds = new Set(duplicateExcessSaleItemIds(items));
  const map = {};
  for (const item of items) {
    const refundable = saleItemRefundableQuantity(item);
    map[item.id] = excessIds.has(item.id) ? refundable : 0;
  }
  return map;
}
