/**
 * Shared helpers for expense list filters and category resolution.
 */

/** Values that must not be sent as API filter params. */
export function isUsableFilterValue(value) {
  if (value == null) return false;
  const s = String(value).trim();
  return s !== '' && s !== 'undefined' && s !== 'null';
}

export function buildExpenseListParams({ filters = {}, page = 1, pageSize = 20 } = {}) {
  const params = {
    page,
    page_size: pageSize,
  };
  if (isUsableFilterValue(filters.category)) params.category = filters.category;
  if (isUsableFilterValue(filters.status)) params.status = filters.status;
  if (isUsableFilterValue(filters.date_from)) params.date_from = filters.date_from;
  if (isUsableFilterValue(filters.date_to)) params.date_to = filters.date_to;
  if (isUsableFilterValue(filters.payment_method)) {
    params.payment_method = filters.payment_method;
  }
  if (isUsableFilterValue(filters.search)) params.search = filters.search;
  return params;
}

export function normalizeFilterChangeValue(value) {
  return isUsableFilterValue(value) ? String(value) : '';
}

export function findCategoryByName(categories, name) {
  const needle = String(name || '')
    .trim()
    .toLowerCase();
  if (!needle) return null;
  return (
    (categories || []).find(
      (cat) => String(cat.name || '').trim().toLowerCase() === needle
    ) || null
  );
}
