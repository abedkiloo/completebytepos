import {
  partitionCategories,
  flattenCategoryTree,
  filterCategoriesForSearch,
  filterByLevel,
} from './categoryTree';

describe('categoryTree', () => {
  const sample = [
    { id: 1, name: 'Furniture', parent: null },
    { id: 2, name: 'Sofas', parent: 1 },
    { id: 3, name: 'Electronics', parent: null },
    { id: 4, name: 'Phones', parent: 3 },
  ];

  it('partitions parents and children', () => {
    const { parents, childrenByParent } = partitionCategories(sample);
    expect(parents.map((p) => p.id)).toEqual([3, 1]);
    expect(childrenByParent[1]).toHaveLength(1);
    expect(childrenByParent[1][0].name).toBe('Sofas');
  });

  it('flattens with depth', () => {
    const { parents, childrenByParent, orphans } = partitionCategories(sample);
    const rows = flattenCategoryTree(parents, childrenByParent, orphans);
    expect(rows[0].depth).toBe(0);
    expect(rows[1].depth).toBe(1);
    expect(rows.find((r) => r.category.name === 'Sofas')?.parentName).toBe('Furniture');
  });

  it('search includes parent when child matches', () => {
    const filtered = filterCategoriesForSearch(sample, 'sofa');
    expect(filtered.map((c) => c.id).sort()).toEqual([1, 2]);
  });

  it('filterByLevel subcategories only', () => {
    const subs = filterByLevel(sample, 'subcategories');
    expect(subs).toHaveLength(2);
  });
});
