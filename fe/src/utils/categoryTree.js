/**
 * Helpers for two-level category trees (parent + subcategory).
 */

export function partitionCategories(categories = []) {
  const parents = [];
  const childrenByParent = {};
  const orphans = [];

  for (const cat of categories) {
    if (!cat.parent) {
      parents.push(cat);
      continue;
    }
    const parentId = cat.parent;
    if (!childrenByParent[parentId]) {
      childrenByParent[parentId] = [];
    }
    childrenByParent[parentId].push(cat);
  }

  parents.sort((a, b) => a.name.localeCompare(b.name));
  Object.values(childrenByParent).forEach((list) => {
    list.sort((a, b) => a.name.localeCompare(b.name));
  });

  const parentIds = new Set(parents.map((p) => p.id));
  for (const cat of categories) {
    if (cat.parent && !parentIds.has(cat.parent)) {
      orphans.push(cat);
    }
  }
  orphans.sort((a, b) => a.name.localeCompare(b.name));

  return { parents, childrenByParent, orphans };
}

/**
 * Flatten tree for table display (parent row, then indented children).
 */
export function flattenCategoryTree(parents, childrenByParent, orphans = []) {
  const rows = [];

  for (const parent of parents) {
    rows.push({
      category: parent,
      depth: 0,
      isParent: true,
    });
    const children = childrenByParent[parent.id] || [];
    for (const child of children) {
      rows.push({
        category: child,
        depth: 1,
        isParent: false,
        parentName: parent.name,
      });
    }
  }

  for (const orphan of orphans) {
    rows.push({
      category: orphan,
      depth: 1,
      isParent: false,
      parentName: null,
      isOrphan: true,
    });
  }

  return rows;
}

export function normalizeCategorySearchText(value) {
  return (value || '').toLowerCase().replace(/\s+/g, ' ').trim();
}

function matchesSearch(category, query) {
  const q = normalizeCategorySearchText(query);
  if (!q) return true;
  const name = normalizeCategorySearchText(category.name);
  const description = normalizeCategorySearchText(category.description);
  return name.includes(q) || (description && description.includes(q));
}

/**
 * Filter categories for search while keeping parent/child groups intact.
 */
export function filterCategoriesForSearch(categories, searchQuery) {
  if (!searchQuery?.trim()) {
    return categories;
  }
  const query = searchQuery.trim();
  const { parents, childrenByParent, orphans } = partitionCategories(categories);
  const matchedIds = new Set();

  for (const parent of parents) {
    const children = childrenByParent[parent.id] || [];
    const parentMatch = matchesSearch(parent, query);
    const matchingChildren = children.filter((c) => matchesSearch(c, query));
    if (parentMatch || matchingChildren.length > 0) {
      matchedIds.add(parent.id);
      if (parentMatch) {
        children.forEach((c) => matchedIds.add(c.id));
      } else {
        matchingChildren.forEach((c) => matchedIds.add(c.id));
      }
    }
  }

  for (const orphan of orphans) {
    if (matchesSearch(orphan, query)) {
      matchedIds.add(orphan.id);
    }
  }

  return categories.filter((c) => matchedIds.has(c.id));
}

export function filterByLevel(categories, level) {
  if (level === 'parents') {
    return categories.filter((c) => !c.parent);
  }
  if (level === 'subcategories') {
    return categories.filter((c) => !!c.parent);
  }
  return categories;
}
