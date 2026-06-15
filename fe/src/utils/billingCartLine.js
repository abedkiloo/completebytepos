/**
 * Build a billing POS cart line from a catalog product and optional variant picker payload.
 */
import { normalizeProductForSale } from './moduleFeatures';

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

function capLineQuantity(line, validateStock = true) {
  if (!validateStock || line.track_stock === false) return line;
  const cap = parseFloat(line.stock_quantity);
  if (Number.isNaN(cap)) return line;
  if (line.quantity > cap) {
    return { ...line, quantity: Math.max(0, cap) };
  }
  return line;
}

/** Rebuild a billing cart line from a server holding sale item. */
export function holdingSaleItemToCartLine(item, { validateStock = true } = {}) {
  const product = item.product || {};
  const qty = Math.max(1, parseInt(item.quantity, 10) || 1);
  const line = normalizeProductForSale({
    id: product.id || item.product_id,
    name: item.product_name || product.name || 'Product',
    sku: item.product_sku || product.sku,
    price: parseFloat(item.unit_price),
    cost: parseFloat(product.cost || 0),
    stock_quantity: product.stock_quantity,
    track_stock: product.track_stock !== false,
    has_variants: product.has_variants,
    variants: product.variants,
  });
  const selling = parseFloat(item.unit_price);
  const mrp = parseFloat(product.mrp) || selling;
  return capLineQuantity(
    {
      ...line,
      quantity: qty,
      variant_id: item.variant?.id || item.variant_id || null,
      mrp,
      selling_price: selling,
      price: selling,
    },
    validateStock
  );
}
