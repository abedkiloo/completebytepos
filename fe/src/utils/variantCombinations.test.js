import {
  buildVariantCombinations,
  combinationsPayloadFromKeys,
  combinationKeyFromParts,
  mergeVariantCombinationRows,
  parseCombinationKey,
  unionSizeColorIdsFromKeys,
  variantCombinationKey,
  variantDisplayLabel,
} from './variantCombinations';

describe('variantCombinations', () => {
  test('buildVariantCombinations creates size × color grid', () => {
    expect(buildVariantCombinations([1, 2], [10])).toEqual([
      { key: '1-10', sizeId: 1, colorId: 10 },
      { key: '2-10', sizeId: 2, colorId: 10 },
    ]);
  });

  test('variantDisplayLabel joins size and color', () => {
    expect(
      variantDisplayLabel({ id: 1, size_name: 'Medium', color_name: 'White' })
    ).toBe('Medium / White');
  });

  test('combinationKeyFromParts and parseCombinationKey round-trip', () => {
    expect(combinationKeyFromParts(2, 10)).toBe('2-10');
    expect(parseCombinationKey('2-10')).toEqual({
      key: '2-10',
      sizeId: 2,
      colorId: 10,
    });
  });

  test('unionSizeColorIdsFromKeys collects unique ids', () => {
    expect(unionSizeColorIdsFromKeys(['1-10', '2-10', '2-11'])).toEqual({
      sizeIds: [1, 2],
      colorIds: [10, 11],
    });
  });

  test('combinationsPayloadFromKeys builds API payload', () => {
    expect(combinationsPayloadFromKeys(['1-10'])).toEqual([{ size: 1, color: 10 }]);
  });

  test('mergeVariantCombinationRows marks missing API rows as pending', () => {
    const rows = mergeVariantCombinationRows(
      [{ id: 5, size: 1, color: 10, price: '50' }],
      [1, 2],
      [10],
      [{ id: 1, name: 'Medium' }, { id: 2, name: 'Large' }],
      [{ id: 10, name: 'White' }]
    );
    expect(rows).toHaveLength(2);
    expect(rows[0].isPending).toBe(false);
    expect(rows[1].isPending).toBe(true);
    expect(rows[1].sizeName).toBe('Large');
    expect(variantCombinationKey(rows[0].variant)).toBe('1-10');
  });
});
