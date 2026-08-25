/** Variant-aware stock alert helpers (mirrors backend stock_alerts). */

export function variantEffectiveThreshold(variant, product) {
  if (variant?.low_stock_threshold != null && variant.low_stock_threshold !== '') {
    return parseInt(variant.low_stock_threshold, 10) || 0;
  }
  return parseInt(product?.low_stock_threshold, 10) || 0;
}

export function variantIsOutOfStock(variant) {
  return variant?.is_active !== false && (parseInt(variant?.stock_quantity, 10) || 0) <= 0;
}

export function variantIsLowStock(variant, product) {
  const qty = parseInt(variant?.stock_quantity, 10) || 0;
  if (qty <= 0) return false;
  const threshold = variantEffectiveThreshold(variant, product);
  return threshold > 0 && qty <= threshold;
}

export function productHasOutOfStock(product) {
  if (!product?.track_stock) return false;
  if (product.has_out_of_stock != null) return Boolean(product.has_out_of_stock);
  if (!product.has_variants) {
    return (parseInt(product.stock_quantity, 10) || 0) <= 0;
  }
  const variants = Array.isArray(product.variants) ? product.variants : [];
  if (variants.length) {
    return variants.some((variant) => variantIsOutOfStock(variant));
  }
  return false;
}

export function productHasLowStock(product) {
  if (!product?.track_stock) return false;
  if (product.is_low_stock != null && !product.has_variants) {
    return Boolean(product.is_low_stock);
  }
  if (!product.has_variants) {
    const qty = parseInt(product.stock_quantity, 10) || 0;
    if (qty <= 0) return false;
    const threshold = parseInt(product.low_stock_threshold, 10) || 0;
    return threshold > 0 && qty <= threshold;
  }
  const variants = Array.isArray(product.variants) ? product.variants : [];
  if (variants.length) {
    return variants.some((variant) => variantIsLowStock(variant, product));
  }
  return Boolean(product.is_low_stock);
}

export function variantStockTone(variant, product) {
  if (variantIsOutOfStock(variant)) return 'destructive';
  if (variantIsLowStock(variant, product)) return 'warning';
  return 'default';
}

/**
 * When stock alert filters are on, only keep matching variant rows.
 * Simple products (no variants) are handled at the product-list level.
 */
export function filterVariantsForStockAlert(
  variants,
  product,
  { outOfStock = false, lowStock = false } = {}
) {
  const list = Array.isArray(variants) ? variants : [];
  if (!outOfStock && !lowStock) return list;
  return list.filter((variant) => {
    if (outOfStock && variantIsOutOfStock(variant)) return true;
    if (lowStock && variantIsLowStock(variant, product)) return true;
    return false;
  });
}

export function summaryFilterFromCard(label) {
  switch (label) {
    case 'Active':
      return { is_active: 'true', low_stock: false, out_of_stock: false };
    case 'Low stock':
      return { is_active: '', low_stock: true, out_of_stock: false };
    case 'Out of stock':
      return { is_active: '', low_stock: false, out_of_stock: true };
    default:
      return { is_active: '', low_stock: false, out_of_stock: false };
  }
}

export function parseProductFiltersFromSearch(searchParams) {
  const lowStock = searchParams.get('low_stock') === 'true';
  const outOfStock = searchParams.get('out_of_stock') === 'true';
  const active = searchParams.get('is_active');
  if (!lowStock && !outOfStock && active !== 'true' && active !== 'false') {
    return null;
  }
  return {
    low_stock: lowStock,
    out_of_stock: outOfStock,
    is_active: active === 'true' ? 'true' : active === 'false' ? 'false' : '',
  };
}

export function productFiltersToSearchParams(filters) {
  const params = new URLSearchParams();
  if (filters.low_stock) params.set('low_stock', 'true');
  if (filters.out_of_stock) params.set('out_of_stock', 'true');
  if (filters.is_active) params.set('is_active', filters.is_active);
  return params;
}
