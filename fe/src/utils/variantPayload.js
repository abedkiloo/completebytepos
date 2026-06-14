/** Full variant body for PUT — prefer ``buildVariantPatchPayload`` for edits. */
export function buildVariantUpdatePayload(variant, draft) {
  const price = draft.price === '' ? null : draft.price;
  const mrp = draft.mrp !== undefined ? (draft.mrp === '' ? null : draft.mrp) : (variant.mrp ?? null);
  const cost =
    draft.cost !== undefined ? (draft.cost === '' ? null : draft.cost) : (variant.cost ?? null);
  return {
    product: variant.product,
    size: variant.size ?? null,
    color: variant.color ?? null,
    sku: variant.sku,
    barcode: variant.barcode ?? null,
    mrp,
    cost,
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
  if (draft.mrp !== undefined) {
    const mrp = draft.mrp === '' ? null : draft.mrp;
    const prev = variant.mrp ?? null;
    if (String(mrp ?? '') !== String(prev ?? '')) {
      payload.mrp = mrp;
    }
  }
  if (draft.stock_quantity !== undefined && draft.stock_quantity !== '') {
    const stock = parseInt(draft.stock_quantity, 10) || 0;
    const prev = parseInt(variant.stock_quantity, 10) || 0;
    if (stock !== prev) {
      payload.stock_quantity = stock;
    }
  }
  if (draft.cost !== undefined) {
    const cost = draft.cost === '' ? null : draft.cost;
    const prev = variant.cost ?? null;
    if (String(cost ?? '') !== String(prev ?? '')) {
      payload.cost = cost;
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
  if (draft.mrp !== undefined && draft.mrp !== '') {
    payload.mrp = draft.mrp;
  }
  if (draft.stock_quantity !== undefined && draft.stock_quantity !== '') {
    payload.stock_quantity = parseInt(draft.stock_quantity, 10) || 0;
  }
  if (draft.cost !== undefined && draft.cost !== '') {
    payload.cost = draft.cost === '' ? null : draft.cost;
  }
  if (draft.is_active !== undefined) {
    payload.is_active = draft.is_active !== false;
  }
  return payload;
}

/**
 * Client-side price/cost/MRP checks before variant save.
 * @returns {string|null} Error message, or null when valid.
 */
export function variantFinancialValidationMessage(
  draft,
  { label = 'this variant', canEditMrp = false } = {}
) {
  const priceNum = parseFloat(draft.price);
  const costNum = parseFloat(draft.cost);
  if (
    draft.cost !== undefined &&
    draft.cost !== '' &&
    draft.price !== undefined &&
    draft.price !== '' &&
    Number.isFinite(priceNum) &&
    Number.isFinite(costNum) &&
    priceNum < costNum
  ) {
    return (
      `Selling price should be greater than or equal to cost price for variant ${label}.`
    );
  }

  const mrpNum = parseFloat(draft.mrp);
  if (
    canEditMrp &&
    draft.mrp !== '' &&
    draft.mrp != null &&
    Number.isFinite(mrpNum) &&
    mrpNum > 0 &&
    Number.isFinite(priceNum) &&
    mrpNum < priceNum
  ) {
    return `MRP should be at least the selling price for variant ${label}.`;
  }

  return null;
}
