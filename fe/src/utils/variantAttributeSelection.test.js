import {
  clearAttributeSelection,
  mergeAttributeSelection,
  toggleAttributeSelection,
} from './variantAttributeSelection';

describe('variantAttributeSelection', () => {
  test('toggleAttributeSelection adds and removes ids', () => {
    expect(toggleAttributeSelection([], 3)).toEqual([3]);
    expect(toggleAttributeSelection([3], 3)).toEqual([]);
    expect(toggleAttributeSelection([1, 2], 3)).toEqual([1, 2, 3]);
  });

  test('mergeAttributeSelection unions without duplicates', () => {
    expect(mergeAttributeSelection([1], [2, 3])).toEqual([1, 2, 3]);
    expect(mergeAttributeSelection([1, 2], [2, 4])).toEqual([1, 2, 4]);
  });

  test('clearAttributeSelection returns empty array', () => {
    expect(clearAttributeSelection()).toEqual([]);
  });
});
