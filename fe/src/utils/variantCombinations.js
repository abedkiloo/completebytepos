/** Build size × color rows matching backend variant generation. */

export function buildVariantCombinations(sizeIds = [], colorIds = []) {
  const sizes = sizeIds?.length ? sizeIds.map(Number) : [null];
  const colors = colorIds?.length ? colorIds.map(Number) : [null];
  const rows = [];

  for (const sizeId of sizes) {
    for (const colorId of colors) {
      const key = `${sizeId ?? 'none'}-${colorId ?? 'none'}`;
      rows.push({ key, sizeId, colorId });
    }
  }

  return rows;
}

export function variantCombinationKey(variant) {
  return `${variant.size ?? 'none'}-${variant.color ?? 'none'}`;
}

export function mergeVariantCombinationRows(variants, sizeIds, colorIds, sizes = [], colors = []) {
  const combinations = buildVariantCombinations(sizeIds, colorIds);
  const byKey = new Map(
    (variants || []).map((variant) => [variantCombinationKey(variant), variant])
  );

  return combinations.map(({ key, sizeId, colorId }) => {
    const variant = byKey.get(key) || null;
    const size = sizes.find((s) => s.id === sizeId);
    const color = colors.find((c) => c.id === colorId);
    return {
      key,
      sizeId,
      colorId,
      variant,
      isPending: !variant,
      sizeName: size?.name,
      colorName: color?.name,
    };
  });
}

export function variantDisplayLabel(variant) {
  if (!variant) return 'Variant';
  const parts = [];
  if (variant.size_name) parts.push(variant.size_name);
  if (variant.color_name) parts.push(variant.color_name);
  return parts.length ? parts.join(' / ') : variant.sku || `Variant #${variant.id}`;
}

export function combinationKeyFromParts(sizeId, colorId) {
  return `${sizeId ?? 'none'}-${colorId ?? 'none'}`;
}

export function parseCombinationKey(key) {
  const [sizePart, colorPart] = String(key).split('-');
  return {
    key,
    sizeId: sizePart === 'none' ? null : Number(sizePart),
    colorId: colorPart === 'none' ? null : Number(colorPart),
  };
}

export function unionSizeColorIdsFromKeys(keys = []) {
  const sizeIds = new Set();
  const colorIds = new Set();
  keys.forEach((key) => {
    const { sizeId, colorId } = parseCombinationKey(key);
    if (sizeId) sizeIds.add(sizeId);
    if (colorId) colorIds.add(colorId);
  });
  return {
    sizeIds: [...sizeIds],
    colorIds: [...colorIds],
  };
}

export function combinationsPayloadFromKeys(keys = []) {
  return keys.map((key) => {
    const { sizeId, colorId } = parseCombinationKey(key);
    return { size: sizeId, color: colorId };
  });
}

export function buildRowFromKey(key, variants = [], sizes = [], colors = []) {
  const { sizeId, colorId } = parseCombinationKey(key);
  const variant =
    variants.find((v) => variantCombinationKey(v) === key) || null;
  const size = sizeId ? sizes.find((s) => Number(s.id) === sizeId) : null;
  const color = colorId ? colors.find((c) => Number(c.id) === colorId) : null;
  return {
    key,
    sizeId,
    colorId,
    variant,
    isPending: !variant,
    sizeName: size?.name,
    colorName: color?.name,
  };
}

export function combinationRowLabel(row) {
  const parts = [];
  if (row.sizeName) parts.push(row.sizeName);
  if (row.colorName) parts.push(row.colorName);
  if (parts.length) return parts.join(' / ');
  if (row.variant) {
    return row.variant.size_name || row.variant.color_name
      ? [row.variant.size_name, row.variant.color_name].filter(Boolean).join(' / ')
      : `Variant #${row.variant.id}`;
  }
  return 'Variant';
}
