/** POS cart recovery — prompt when returning with an in-progress sale. */

export const DRAFT_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

export function countHoldingItems(holding) {
  if (!holding?.items?.length) return 0;
  return holding.items.reduce(
    (sum, line) => sum + Math.max(0, parseInt(line.quantity, 10) || 0),
    0
  );
}

export function holdingNeedsRecoveryPrompt(holding) {
  return countHoldingItems(holding) > 0;
}

export const shouldPromptForHoldingRecovery = holdingNeedsRecoveryPrompt;

export function localDraftNeedsRecoveryPrompt(draft) {
  if (!draft?.cart?.length) return false;
  const hasLines = draft.cart.some(
    (line) => (parseInt(line.quantity, 10) || 0) > 0
  );
  if (!hasLines) return false;
  const savedAt = draft.savedAt;
  if (!savedAt) return true;
  return Date.now() - savedAt <= DRAFT_MAX_AGE_MS;
}

/**
 * @param {{ source: 'holding'|'local', itemCount: number, label?: string }} meta
 */
export function buildCartRecoveryMessage({ source, itemCount, label }) {
  const countLabel = itemCount === 1 ? '1 item' : `${itemCount} items`;
  if (source === 'holding') {
    const ref = label ? ` (${label})` : '';
    return `You have an open draft invoice${ref} with ${countLabel} in the cart. Continue this sale or start a new one?`;
  }
  return `You had ${countLabel} in the register from your last visit. Continue this sale or start a new one?`;
}

export function posCartDraftKey(userId, branchId) {
  return `pos_cart_draft_u${userId ?? '0'}_b${branchId ?? '0'}`;
}

export function serializeRetailCartDraft({
  cart,
  selectedCustomer,
  taxPct = 0,
  discount = 0,
  discountType = 'flat',
  paymentMethod = 'cash',
}) {
  return {
    version: 1,
    savedAt: Date.now(),
    cart: (cart || []).map((line) => ({
      id: line.id,
      name: line.name,
      sku: line.sku,
      price: line.price,
      mrp: line.mrp,
      selling_price: line.selling_price,
      cost: line.cost,
      quantity: line.quantity,
      variant_id: line.variant_id ?? null,
      stock_quantity: line.stock_quantity,
      track_stock: line.track_stock,
      has_variants: line.has_variants,
    })),
    selectedCustomer: selectedCustomer
      ? { id: selectedCustomer.id, name: selectedCustomer.name }
      : null,
    taxPct,
    discount,
    discountType,
    paymentMethod,
  };
}

export function loadRetailCartDraft(key, storage = sessionStorage) {
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || parsed.version !== 1) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveRetailCartDraft(key, draft, storage = sessionStorage) {
  try {
    storage.setItem(key, JSON.stringify(draft));
  } catch {
    /* quota / private mode */
  }
}

export function clearRetailCartDraft(key, storage = sessionStorage) {
  try {
    storage.removeItem(key);
  } catch {
    /* ignore */
  }
}

export function countLocalDraftItems(draft) {
  if (!draft?.cart?.length) return 0;
  return draft.cart.reduce(
    (sum, line) => sum + Math.max(0, parseInt(line.quantity, 10) || 0),
    0
  );
}

/** Branch id from login payload for per-register draft keys. */
export function resolveBranchIdFromUser(user) {
  if (!user) return null;
  const branch = user.profile?.branch;
  if (branch && typeof branch === 'object') return branch.id ?? null;
  return user.profile?.branch_id ?? null;
}
