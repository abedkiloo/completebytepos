/**
 * Catalogue sellable quantity (mirrors backend ``sellable_stock_quantity``).
 * Use for list/POS normalization when stock may live on parent, variant rows, or both.
 */

export function aggregateActiveVariantStock(variants) {
  const list = Array.isArray(variants) ? variants : [];
  return list
    .filter((v) => v.is_active !== false)
    .reduce((sum, v) => sum + (parseInt(v.stock_quantity, 10) || 0), 0);
}

export function catalogSellableStock(product) {
  if (!product) return 0;
  const parent = parseInt(product.stock_quantity, 10) || 0;
  if (!product.has_variants) return parent;
  const variants = product.variants;
  if (!Array.isArray(variants) || variants.length === 0) return parent;
  return Math.max(parent, aggregateActiveVariantStock(variants));
}
