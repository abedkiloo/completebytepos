/**
 * Product pricing helpers.
 * Selling price is the single amount used for POS, sales lines, invoices, and reports.
 */

export function getSellingPrice(product) {
  if (!product) return 0;
  const raw = product.selling_price ?? product.price ?? 0;
  const n = parseFloat(raw);
  return Number.isFinite(n) ? n : 0;
}

export function getMrp(product) {
  if (!product) return 0;
  const selling = getSellingPrice(product);
  const raw = product.mrp ?? selling;
  const n = parseFloat(raw);
  return Number.isFinite(n) ? n : selling;
}

/** Normalize API product for cart/catalog — `price` is always selling price. */
export function withSellingPriceFields(product) {
  if (!product) return product;
  const selling = getSellingPrice(product);
  const mrp = getMrp(product);
  return {
    ...product,
    mrp,
    selling_price: selling,
    price: selling,
  };
}
