import {
  crossParentSubcategoryHint,
  mergeCategoryOptions,
} from './categorySelectHelpers';

describe('categorySelect helpers', () => {
  test('mergeCategoryOptions dedupes by id', () => {
    const merged = mergeCategoryOptions(
      [{ id: 1, name: 'A' }],
      [{ id: 1, name: 'A' }, { id: 2, name: 'B' }]
    );
    expect(merged).toHaveLength(2);
    expect(merged.map((r) => r.id)).toEqual([1, 2]);
  });

  test('crossParentSubcategoryHint explains different parent', () => {
    const hint = crossParentSubcategoryHint(
      { id: 5, name: 'SLANDING', parent: 2 },
      9,
      'Tables'
    );
    expect(hint).toMatch(/SLANDING/);
    expect(hint).toMatch(/Tables/);
    expect(hint).toMatch(/unique store-wide/i);
  });

  test('crossParentSubcategoryHint empty for same parent', () => {
    expect(
      crossParentSubcategoryHint({ id: 5, name: 'SLANDING', parent: 9 }, 9, 'Sofa')
    ).toBe('');
  });
});
