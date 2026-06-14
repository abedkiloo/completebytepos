/** Labels for product pickers in stock management (Inventory). */

export function formatStockProductOptionLabel(prod) {
  if (!prod) return '';
  const skuPart = prod.sku ? ` (${prod.sku})` : '';
  if (prod.has_variants) {
    return `${prod.name}${skuPart} — variants, total stock ${prod.stock_quantity ?? 0}`;
  }
  return `${prod.name}${skuPart} — stock ${prod.stock_quantity ?? 0}`;
}

export function findProductById(products, productId) {
  if (!productId || !Array.isArray(products)) return null;
  const id = Number(productId);
  return products.find((p) => Number(p.id) === id) || null;
}
