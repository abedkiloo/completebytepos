/** Labels and summary lines for per-variant drafts on product create/edit. */

export function hasVariantDraftContent(draft) {
  if (!draft || typeof draft !== 'object') return false;
  const { stock_quantity: stock, price } = draft;
  const hasStock = stock !== '' && stock !== undefined && stock !== null;
  const hasPrice = price !== '' && price !== undefined && price !== null;
  return hasStock || hasPrice;
}

export function combinationKeyLabel(key, sizes = [], colors = []) {
  const [sizePart, colorPart] = String(key).split('-');
  const sizeId = sizePart === 'none' ? null : Number(sizePart);
  const colorId = colorPart === 'none' ? null : Number(colorPart);
  const parts = [];
  const color = colorId ? colors.find((c) => c.id === colorId) : null;
  const size = sizeId ? sizes.find((s) => s.id === sizeId) : null;
  if (color?.name) parts.push(color.name);
  if (size?.name) parts.push(size.name);
  return parts.length ? parts.join(' / ') : 'Default variant';
}

export function buildVariantDraftSummary(draftsByKey, { sizes = [], colors = [] } = {}) {
  const lines = Object.entries(draftsByKey || {})
    .filter(([, draft]) => hasVariantDraftContent(draft))
    .map(([key, draft]) => {
      const label = combinationKeyLabel(key, sizes, colors);
      const details = [];
      if (draft.price !== '' && draft.price != null) {
        details.push(`price KES ${draft.price}`);
      }
      if (draft.stock_quantity !== '' && draft.stock_quantity != null) {
        details.push(`stock ${draft.stock_quantity}`);
      }
      return { key, label, details, draft };
    })
    .sort((a, b) => a.label.localeCompare(b.label));

  const totalStock = lines.reduce((sum, line) => {
    const n = parseInt(line.draft.stock_quantity, 10);
    return sum + (Number.isFinite(n) ? n : 0);
  }, 0);

  return { lines, totalStock, count: lines.length };
}
