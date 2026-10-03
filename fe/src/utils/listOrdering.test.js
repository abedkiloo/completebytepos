import { LIST_RANK_OPTIONS, sortRecords, toggleListOrdering, withListOrdering } from './listOrdering';

describe('listOrdering', () => {
  test('withListOrdering omits empty default', () => {
    expect(withListOrdering({ page: 1 }, '')).toEqual({ page: 1 });
    expect(withListOrdering({ page: 1 }, 'name')).toEqual({ page: 1, ordering: 'name' });
  });

  test('toggleListOrdering cycles name then reverse then default', () => {
    expect(toggleListOrdering('', 'name')).toBe('name');
    expect(toggleListOrdering('name', 'name')).toBe('-name');
    expect(toggleListOrdering('-name', 'name')).toBe('');
  });

  test('toggleListOrdering prefers newest saved first', () => {
    expect(toggleListOrdering('', 'saved')).toBe('-saved');
    expect(toggleListOrdering('-saved', 'saved')).toBe('saved');
    expect(toggleListOrdering('saved', 'saved')).toBe('');
  });

  test('sortRecords ranks by name and saved date', () => {
    const rows = [
      { name: 'Zebra', created_at: '2026-01-01' },
      { name: 'Apple', created_at: '2026-02-01' },
    ];
    expect(sortRecords(rows, 'name').map((r) => r.name)).toEqual(['Apple', 'Zebra']);
    expect(sortRecords(rows, '-saved').map((r) => r.name)).toEqual(['Apple', 'Zebra']);
    expect(LIST_RANK_OPTIONS.map((o) => o.value)).toEqual(['', 'name', '-name', '-saved', 'saved']);
  });
});
