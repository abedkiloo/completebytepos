import { getSellableStock } from './productStock';

/** Normalize FK ids from API (number, string, or nested object). */
export function normalizeFkId(value) {
  if (value == null) return null;
  if (typeof value === 'object' && value.id != null) return Number(value.id);
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

export function variantMatchesSize(variant, sizeId) {
  const target = normalizeFkId(sizeId);
  if (target == null) return false;
  return (
    normalizeFkId(variant.size) === target ||
    normalizeFkId(variant.size_id) === target
  );
}

export function variantMatchesColor(variant, colorId) {
  const target = normalizeFkId(colorId);
  if (target == null) return false;
  return (
    normalizeFkId(variant.color) === target ||
    normalizeFkId(variant.color_id) === target
  );
}

/**
 * Resolve the variant row for the current size/color picks.
 */
export function findVariantForSelection(
  variants,
  selectedSize,
  selectedColor,
  availableSizes,
  availableColors
) {
  const list = Array.isArray(variants) ? variants : [];
  const sizes = Array.isArray(availableSizes) ? availableSizes : [];
  const colors = Array.isArray(availableColors) ? availableColors : [];

  if (list.length === 0) return null;

  if (sizes.length > 0 && colors.length > 0) {
    if (selectedSize == null || selectedColor == null) return null;
    return (
      list.find(
        (v) =>
          variantMatchesSize(v, selectedSize) &&
          variantMatchesColor(v, selectedColor)
      ) || null
    );
  }

  if (sizes.length > 0 && colors.length === 0) {
    if (selectedSize == null) return null;
    return (
      list.find(
        (v) =>
          variantMatchesSize(v, selectedSize) &&
          normalizeFkId(v.color) == null &&
          normalizeFkId(v.color_id) == null
      ) || null
    );
  }

  if (colors.length > 0 && sizes.length === 0) {
    if (selectedColor == null) return null;
    return (
      list.find(
        (v) =>
          variantMatchesColor(v, selectedColor) &&
          normalizeFkId(v.size) == null &&
          normalizeFkId(v.size_id) == null
      ) || null
    );
  }

  return null;
}

/**
 * Effective sellable quantity for the picker (mirrors backend sellable_stock_quantity).
 * Returns null when stock is not tracked.
 */
function sumActiveVariantStock(variantsList) {
  const list = Array.isArray(variantsList) ? variantsList : [];
  return list
    .filter((v) => v.is_active !== false)
    .reduce((sum, v) => sum + (parseInt(v.stock_quantity, 10) || 0), 0);
}

export function getSellableStockForVariant(
  product,
  selectedVariant,
  variantsList = null
) {
  if (!product || product.track_stock === false) return null;

  const allVariants =
    variantsList ?? (Array.isArray(product.variants) ? product.variants : null);

  if (!selectedVariant) {
    const base = getSellableStock(product);
    return base === null ? null : Math.max(0, base);
  }

  const variantStock = parseInt(selectedVariant.stock_quantity, 10);
  const variantQty = Number.isFinite(variantStock) ? variantStock : 0;
  if (variantQty > 0) {
    return variantQty;
  }

  const parentRaw = parseInt(product.stock_quantity, 10);
  const parentQty = Number.isFinite(parentRaw) ? parentRaw : 0;
  if (!product.has_variants) {
    return variantQty;
  }

  const variantTotal = allVariants ? sumActiveVariantStock(allVariants) : null;
  if (variantTotal === null) {
    return Math.max(parentQty, variantQty);
  }

  if (parentQty > 0 && variantTotal === 0) {
    return parentQty;
  }
  return variantQty;
}

export function getVariantDisplayPrice(product, selectedVariant) {
  if (selectedVariant) {
    return (
      selectedVariant.effective_price ??
      selectedVariant.price ??
      product?.price ??
      0
    );
  }
  return product?.price ?? 0;
}

/**
 * Whether size/color (and matching variant row) are ready to add.
 */
export function canAddVariantToCart({
  product,
  variants,
  selectedSize,
  selectedColor,
  selectedVariant,
  availableSizes,
  availableColors,
}) {
  if (!product?.has_variants) return true;
  const list = Array.isArray(variants) ? variants : [];
  if (list.length === 0) return true;

  const sizes = Array.isArray(availableSizes) ? availableSizes : [];
  const colors = Array.isArray(availableColors) ? availableColors : [];

  if (sizes.length > 0 && colors.length > 0) {
    return (
      selectedSize != null &&
      selectedColor != null &&
      selectedVariant != null
    );
  }
  if (sizes.length > 0 && colors.length === 0) {
    return selectedSize != null && selectedVariant != null;
  }
  if (colors.length > 0 && sizes.length === 0) {
    return selectedColor != null && selectedVariant != null;
  }
  return true;
}

/**
 * Block add only when stock validation is on and effective stock is zero.
 */
export function isVariantAddToCartDisabled({
  product,
  selectedVariant,
  canAdd,
  validateStock = true,
  variantsList = null,
}) {
  if (!canAdd) return true;
  if (!validateStock) return false;
  const stock = getSellableStockForVariant(
    product,
    selectedVariant,
    variantsList
  );
  if (stock === null) return false;
  return stock <= 0;
}

export function buildVariantCartPayload(
  product,
  selectedVariant,
  quantity,
  variantsList = null
) {
  const qty = Math.max(1, parseInt(quantity, 10) || 1);
  const stock = getSellableStockForVariant(
    product,
    selectedVariant,
    variantsList
  );

  if (selectedVariant) {
    return {
      ...product,
      variant_id: selectedVariant.id,
      variant: selectedVariant,
      size: selectedVariant.size_name,
      size_id: normalizeFkId(selectedVariant.size) ?? selectedVariant.size_id,
      color: selectedVariant.color_name,
      color_id: normalizeFkId(selectedVariant.color) ?? selectedVariant.color_id,
      price: parseFloat(
        selectedVariant.effective_price || selectedVariant.price || product.price
      ),
      stock_quantity: stock === null ? null : stock,
      sku: selectedVariant.sku || product.sku || '',
      quantity: qty,
    };
  }

  return {
    ...product,
    price: parseFloat(product.price),
    sku: product.sku || '',
    stock_quantity: stock === null ? null : stock ?? 0,
    quantity: qty,
  };
}
