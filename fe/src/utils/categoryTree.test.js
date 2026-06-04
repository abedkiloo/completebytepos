import {
  partitionCategories,
  flattenCategoryTree,
  filterCategoriesForSearch,
  filterByLevel,
  normalizeCategorySearchText,
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

  it('search is case-insensitive and ignores extra whitespace', () => {
    const withSpaces = [{ id: 5, name: '  Home  Decor  ', parent: null }];
    const filtered = filterCategoriesForSearch(withSpaces, '  home decor  ');
    expect(filtered).toHaveLength(1);
    expect(normalizeCategorySearchText('  Home  Decor  ')).toBe('home decor');
  });

  it('filterByLevel subcategories only', () => {
    const subs = filterByLevel(sample, 'subcategories');
    expect(subs).toHaveLength(2);
  });

  it('filterByLevel all returns unchanged', () => {
    expect(filterByLevel(sample, 'all')).toHaveLength(4);
  });

  it('filterByLevel parents only', () => {
    expect(filterByLevel(sample, 'parents')).toHaveLength(2);
  });

  it('handles orphan subcategories', () => {
    const orphan = { id: 99, name: 'Lost', parent: 999 };
    const { orphans } = partitionCategories([...sample, orphan]);
    expect(orphans).toHaveLength(1);
    const rows = flattenCategoryTree([], {}, orphans);
    expect(rows[0].isOrphan).toBe(true);
    expect(filterCategoriesForSearch([orphan], 'lost')).toHaveLength(1);
  });

  it('search returns all when query empty', () => {
    expect(filterCategoriesForSearch(sample, '')).toHaveLength(4);
    expect(filterCategoriesForSearch(sample, '   ')).toHaveLength(4);
  });

  it('search includes all children when parent matches', () => {
    const filtered = filterCategoriesForSearch(sample, 'furniture');
    expect(filtered.map((c) => c.id).sort()).toEqual([1, 2]);
  });

  it('search keeps parent when only child matches', () => {
    const filtered = filterCategoriesForSearch(sample, 'phones');
    expect(filtered.map((c) => c.id).sort()).toEqual([3, 4]);
  });

  it('search matches description', () => {
    const data = [
      { id: 1, name: 'A', parent: null, description: 'alpha group' },
      { id: 2, name: 'B', parent: 1 },
    ];
    const filtered = filterCategoriesForSearch(data, 'alpha');
    expect(filtered.map((c) => c.id)).toContain(1);
  });
});
