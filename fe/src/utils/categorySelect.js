import { categoriesAPI } from '../services/api';
import { crossParentSubcategoryHint, mergeCategoryOptions } from './categorySelectHelpers';

export { crossParentSubcategoryHint, mergeCategoryOptions };

function unwrapList(response) {
  const data = response?.data?.results ?? response?.data ?? [];
  return Array.isArray(data) ? data : [];
}

/**
 * Load subcategories for a parent, optionally filtered by search term (server-side).
 */
export async function fetchSubcategories(parentId, { search = '', isActive = true } = {}) {
  if (!parentId) return [];
  const params = {
    parent: parseInt(parentId, 10),
    is_active: isActive ? 'true' : 'false',
  };
  const term = (search || '').trim();
  if (term) {
    params.search = term;
  }
  const response = await categoriesAPI.list(params);
  return unwrapList(response);
}

/**
 * Case-insensitive exact name lookup — finds a category anywhere in the tree.
 */
export async function findCategoryByExactName(name, { isActive = true } = {}) {
  const term = (name || '').trim();
  if (!term) return null;
  const params = { exact_name: term };
  if (isActive) {
    params.is_active = 'true';
  }
  const response = await categoriesAPI.list(params);
  const rows = unwrapList(response);
  return rows[0] || null;
}

/**
 * If a duplicate name already exists under the same parent, return it for auto-select.
 */
export async function resolveSubcategoryDuplicate(name, parentId) {
  const existing = await findCategoryByExactName(name);
  if (!existing || !parentId) return null;
  if (String(existing.parent) !== String(parentId)) {
    return { existing, sameParent: false };
  }
  return { existing, sameParent: true };
}

