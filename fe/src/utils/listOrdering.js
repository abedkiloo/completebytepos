export const LIST_RANK_OPTIONS = [
  { value: '', label: 'Default' },
  { value: 'name', label: 'Name A–Z' },
  { value: '-name', label: 'Name Z–A' },
  { value: '-saved', label: 'Newest saved' },
  { value: 'saved', label: 'Oldest saved' },
];

export function withListOrdering(params = {}, ordering) {
  const next = { ...params };
  if (ordering) next.ordering = ordering;
  return next;
}

export function toggleListOrdering(current, key) {
  const asc = key;
  const desc = `-${key}`;
  if (key === 'saved') {
    if (current === desc) return asc;
    if (current === asc) return '';
    return desc;
  }
  if (current === asc) return desc;
  if (current === desc) return '';
  return asc;
}

export function sortRecords(rows, ordering, { nameKey = 'name', savedKey = 'created_at' } = {}) {
  if (!ordering || !Array.isArray(rows)) return rows;
  const descending = ordering.startsWith('-');
  const key = ordering.replace(/^-/, '');
  const field = key === 'saved' || key === 'created_at' ? savedKey : nameKey;
  const copy = [...rows];
  copy.sort((a, b) => {
    const left = a?.[field] ?? '';
    const right = b?.[field] ?? '';
    const cmp = String(left).localeCompare(String(right), undefined, {
      numeric: true,
      sensitivity: 'base',
    });
    return descending ? -cmp : cmp;
  });
  return copy;
}
