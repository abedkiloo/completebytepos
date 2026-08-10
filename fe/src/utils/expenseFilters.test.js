import {
  buildExpenseListParams,
  findCategoryByName,
  isUsableFilterValue,
  normalizeFilterChangeValue,
} from './expenseFilters';

describe('expenseFilters', () => {
  it('rejects empty and sentinel filter values', () => {
    expect(isUsableFilterValue('')).toBe(false);
    expect(isUsableFilterValue('undefined')).toBe(false);
    expect(isUsableFilterValue('null')).toBe(false);
    expect(isUsableFilterValue(12)).toBe(true);
    expect(isUsableFilterValue('approved')).toBe(true);
  });

  it('omits bad filter values from list params', () => {
    expect(
      buildExpenseListParams({
        filters: {
          category: 'undefined',
          status: '',
          payment_method: 'cash',
          search: 'rent',
        },
        page: 2,
        pageSize: 25,
      })
    ).toEqual({
      page: 2,
      page_size: 25,
      payment_method: 'cash',
      search: 'rent',
    });
  });

  it('normalizes select clear to empty string', () => {
    expect(normalizeFilterChangeValue('undefined')).toBe('');
    expect(normalizeFilterChangeValue('pending')).toBe('pending');
  });

  it('finds categories by case-insensitive name', () => {
    const cats = [{ id: 1, name: 'Office Supplies' }];
    expect(findCategoryByName(cats, 'office supplies')?.id).toBe(1);
    expect(findCategoryByName(cats, 'Missing')).toBeNull();
  });
});
