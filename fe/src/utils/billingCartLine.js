/**
 * Build a billing POS cart line from a catalog product and optional variant picker payload.
 */
export function resolveCartVariantId(productId, variantPayload) {
  if (variantPayload == null) return null;
  if (variantPayload.variant_id != null && variantPayload.variant_id !== '') {
    return variantPayload.variant_id;
  }
  if (variantPayload.variant?.id != null) {
    return variantPayload.variant.id;
  }
  const rawId = variantPayload.id;
  if (rawId != null && Number(rawId) !== Number(productId)) {
    return rawId;
  }
  return null;
}

export function buildBillingCartLine(product, variantPayload = null, { validateStock = true } = {}) {
  const baseId = product?.id;
  const merged =
    variantPayload && (variantPayload.variant_id != null || variantPayload.variant)
      ? { ...product, ...variantPayload }
      : { ...product };

  const variantId = resolveCartVariantId(baseId, variantPayload);
  const variantRow = variantPayload?.variant ?? null;

  const selling = parseFloat(
    merged.price ??
      merged.selling_price ??
      variantRow?.effective_price ??
      variantRow?.price ??
      product?.price ??
      0
  );
  const mrp = parseFloat(
    merged.mrp ??
      variantRow?.effective_mrp ??
      variantRow?.mrp ??
      product?.mrp ??
      selling
  );

  const stockQuantity =
    merged.stock_quantity ??
    variantRow?.stock_quantity ??
    product?.stock_quantity;

  return {
    id: baseId,
    name: merged.name ?? product?.name,
    sku: merged.sku ?? variantRow?.sku ?? product?.sku,
    mrp,
    selling_price: selling,
    price: selling,
    cost: parseFloat(variantRow?.cost ?? merged.cost ?? product?.cost ?? 0),
    quantity: Math.max(1, parseInt(merged.quantity, 10) || 1),
    variant_id: variantId,
    stock_quantity: stockQuantity,
    track_stock: merged.track_stock !== false && product?.track_stock !== false,
    has_variants: Boolean(product?.has_variants),
    validateStock,
  };
}
