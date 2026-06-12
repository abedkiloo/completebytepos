/** Full variant body for PUT — prefer ``buildVariantPatchPayload`` for edits. */
export function buildVariantUpdatePayload(variant, draft) {
  const price = draft.price === '' ? null : draft.price;
  return {
    product: variant.product,
    size: variant.size ?? null,
    color: variant.color ?? null,
    sku: variant.sku,
    barcode: variant.barcode ?? null,
    mrp: variant.mrp ?? null,
    cost: variant.cost ?? null,
    low_stock_threshold: variant.low_stock_threshold ?? null,
    price,
    selling_price: price,
    stock_quantity: parseInt(draft.stock_quantity, 10) || 0,
    is_active: draft.is_active !== false,
  };
}

/**
 * PATCH body with only fields that changed — avoids rewriting other variant data.
 */
export function buildVariantPatchPayload(variant, draft) {
  const payload = {};
  if (draft.price !== undefined) {
    const price = draft.price === '' ? null : draft.price;
    const prev = variant.price ?? variant.selling_price ?? null;
    if (String(price ?? '') !== String(prev ?? '')) {
      payload.price = price;
      payload.selling_price = price;
    }
  }
  if (draft.stock_quantity !== undefined && draft.stock_quantity !== '') {
    const stock = parseInt(draft.stock_quantity, 10) || 0;
    const prev = parseInt(variant.stock_quantity, 10) || 0;
    if (stock !== prev) {
      payload.stock_quantity = stock;
    }
  }
  if (draft.is_active !== undefined) {
    const active = draft.is_active !== false;
    const prev = variant.is_active !== false;
    if (active !== prev) {
      payload.is_active = active;
    }
  }
  return payload;
}

/** Apply initial price/stock from product-create drafts (only set provided fields). */
export function buildVariantDraftPatchPayload(draft) {
  const payload = {};
  if (draft.price !== undefined) {
    const price = draft.price === '' ? null : draft.price;
    payload.price = price;
    payload.selling_price = price;
  }
  if (draft.stock_quantity !== undefined && draft.stock_quantity !== '') {
    payload.stock_quantity = parseInt(draft.stock_quantity, 10) || 0;
  }
  if (draft.is_active !== undefined) {
    payload.is_active = draft.is_active !== false;
  }
  return payload;
}
