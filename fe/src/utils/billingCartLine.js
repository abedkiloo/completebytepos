/**
 * Build a billing POS cart line from a catalog product and optional variant picker payload.
 */
import { normalizeProductForSale, isProductVariantsEnabled } from './moduleFeatures';
import { firstFiniteMoney } from './saleUnitPrice';

/**
 * Resolve the catalog selling-price floor from a holding / open-for-correction
 * sale item (nested product + optional variant), not the charged unit price.
 *
 * Prefers product/variant list selling, then MRP, then charged ``unit_price``
 * only when catalog fields are absent — so a markup on the sale does not lock
 * rectify edits to that markup.
 *
 * Args:
 *   item: Holding sale item from SaleSerializer (product + unit_price required
 *     in practice; empty object tolerated). Max nested depth ~3.
 *
 * Returns:
 *   Finite catalog unit price, or NaN when nothing usable is present.
 */
export function resolveHoldingCatalogUnitPrice(item) {
  const product =
    item?.product && typeof item.product === 'object' ? item.product : {};
  const variantsOn = isProductVariantsEnabled();
  const variant =
    variantsOn && item?.variant && typeof item.variant === 'object'
      ? item.variant
      : {};
  return firstFiniteMoney(
    variant.effective_price,
    variant.selling_price,
    variant.price,
    product.selling_price,
    product.price,
    item?.catalog_unit_price,
    variant.effective_mrp,
    variant.mrp,
    product.mrp,
    item?.unit_price
  );
}

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
    catalog_price: selling,
    price: selling,
    cost: parseFloat(variantRow?.cost ?? merged.cost ?? product?.cost ?? 0),
    quantity: Math.max(1, parseInt(merged.quantity, 10) || 1),
    variant_id: variantId,
    variant: variantRow,
    size: merged.size ?? variantRow?.size_name ?? null,
    color: merged.color ?? variantRow?.color_name ?? null,
    size_name: variantRow?.size_name ?? merged.size_name ?? merged.size ?? null,
    color_name: variantRow?.color_name ?? merged.color_name ?? merged.color ?? null,
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

/**
 * Rebuild a billing cart line from a server holding / open-for-correction item.
 *
 * Stamps ``catalog_price`` / ``selling_price`` from catalog (product/variant),
 * and ``price`` from the charged ``unit_price`` so rectify can edit markup
 * down toward list without locking the floor at the charged amount.
 *
 * Args:
 *   item (object): Sale item payload with ``unit_price``, optional nested
 *     ``product`` / ``variant``. Quantity 1–1e6 when present.
 *   options.validateStock (boolean): When true, cap qty to ``stock_quantity``.
 *
 * Returns:
 *   Cart line object ready for billing POS / Correction Mode.
 */
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
  const charged = parseFloat(item.unit_price);
  const catalogPrice = resolveHoldingCatalogUnitPrice(item);
  const catalog = Number.isFinite(catalogPrice)
    ? catalogPrice
    : Number.isFinite(charged)
      ? charged
      : 0;
  const mrp = firstFiniteMoney(product.mrp, item.variant?.effective_mrp, item.variant?.mrp, catalog);
  const variantId = isProductVariantsEnabled()
    ? item.variant?.id || item.variant_id || null
    : null;
  return capLineQuantity(
    {
      ...line,
      quantity: qty,
      variant_id: variantId,
      variant: item.variant || null,
      size_name: item.size_name || item.variant?.size_name || null,
      color_name: item.color_name || item.variant?.color_name || null,
      mrp: Number.isFinite(mrp) ? mrp : catalog,
      // Catalog list selling stays on selling_price / catalog_price; charged
      // override lives only on price so rectify can lower markup toward list.
      selling_price: catalog,
      catalog_price: catalog,
      price: Number.isFinite(charged) ? charged : catalog,
    },
    validateStock
  );
}
