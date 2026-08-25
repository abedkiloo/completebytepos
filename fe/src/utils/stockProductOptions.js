/** Labels and loaders for product pickers in stock management (Inventory). */

import { productsAPI } from '../services/api';

/** Matches backend StandardResultsSetPagination.max_page_size. */
export const STOCK_PRODUCT_PAGE_SIZE = 200;

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

/**
 * Load active stock-tracked products. Prefer `search` so catalogs larger than
 * the page-size cap remain discoverable.
 */
export async function fetchTrackedStockProducts({ search = '' } = {}) {
  const params = {
    track_stock: 'true',
    is_active: 'true',
    page_size: STOCK_PRODUCT_PAGE_SIZE,
  };
  const q = String(search || '').trim();
  if (q) {
    params.search = q;
  }
  const response = await productsAPI.list(params);
  const data = response.data?.results || response.data || [];
  return Array.isArray(data) ? data : [];
}

export function toStockProductSelectOptions(products) {
  return (Array.isArray(products) ? products : []).map((prod) => ({
    id: prod.id,
    name: formatStockProductOptionLabel(prod),
    has_variants: Boolean(prod.has_variants),
  }));
}

export function formatVariantStockOptionLabel(variant, productName = '') {
  if (!variant) return '';
  const bits = [variant.sku, variant.size_name, variant.color_name].filter(Boolean);
  const detail = bits.length ? bits.join(' · ') : `Variant #${variant.id}`;
  const prefix = productName ? `${productName} — ` : '';
  return `${prefix}${detail} — stock ${variant.stock_quantity ?? 0}`;
}
