/** Toggle helpers for size/color checkbox lists on the product form. */

export function toggleAttributeSelection(selectedIds, id) {
  const n = Number(id);
  if (!Number.isFinite(n)) return selectedIds || [];
  const set = new Set((selectedIds || []).map(Number));
  if (set.has(n)) {
    set.delete(n);
  } else {
    set.add(n);
  }
  return [...set];
}

export function mergeAttributeSelection(selectedIds, idsToAdd) {
  const set = new Set((selectedIds || []).map(Number));
  (idsToAdd || []).forEach((id) => {
    const n = Number(id);
    if (Number.isFinite(n)) set.add(n);
  });
  return [...set];
}

export function clearAttributeSelection() {
  return [];
}
