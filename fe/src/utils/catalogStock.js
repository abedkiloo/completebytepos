/**
 * Catalogue sellable quantity (mirrors backend ``sellable_stock_quantity``).
 * Variant products use the sum of active variant rows; simple products use parent stock.
 */

export function aggregateActiveVariantStock(variants) {
  const list = Array.isArray(variants) ? variants : [];
  return list
    .filter((v) => v.is_active !== false)
    .reduce((sum, v) => sum + (parseInt(v.stock_quantity, 10) || 0), 0);
}

export function catalogSellableStock(product) {
  if (!product) return 0;
  if (!product.has_variants) {
    return parseInt(product.stock_quantity, 10) || 0;
  }
  const variants = product.variants;
  if (Array.isArray(variants) && variants.length > 0) {
    return aggregateActiveVariantStock(variants);
  }
  // List/detail API often exposes aggregated variant stock on the parent row only.
  return parseInt(product.stock_quantity, 10) || 0;
}
