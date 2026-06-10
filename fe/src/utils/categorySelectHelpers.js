export function mergeCategoryOptions(existing = [], incoming = []) {
  const byId = new Map();
  for (const row of [...existing, ...incoming]) {
    if (row?.id != null) {
      byId.set(row.id, row);
    }
  }
  return Array.from(byId.values()).sort((a, b) =>
    (a.name || '').localeCompare(b.name || '')
  );
}

/** Hint when search finds nothing locally but the name exists under another parent. */
export function crossParentSubcategoryHint(existing, parentId, parentName = '') {
  if (!existing?.parent || String(existing.parent) === String(parentId)) {
    return '';
  }
  const where = parentName || 'another category';
  return `"${existing.name}" already exists under ${where}. Names must be unique store-wide.`;
}
