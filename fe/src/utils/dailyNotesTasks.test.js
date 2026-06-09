import {
  countOpenTasks,
  formatTaskCompletedAt,
  mergeActivityDates,
  sortDailyTasks,
  taskStatusLabel,
} from './dailyNotesTasks';

describe('dailyNotesTasks', () => {
  test('defaults for empty inputs', () => {
    expect(sortDailyTasks()).toEqual([]);
    expect(countOpenTasks()).toBe(0);
    expect(mergeActivityDates()).toEqual([]);
    expect(taskStatusLabel(null)).toBe('To do');
    expect(taskStatusLabel(undefined)).toBe('To do');
  });

  const open = { id: 1, title: 'A', is_done: false, created_at: '2026-06-01T10:00:00Z' };
  const done = {
    id: 2,
    title: 'B',
    is_done: true,
    completed_at: '2026-06-01T14:00:00Z',
    created_at: '2026-06-01T09:00:00Z',
  };

  test('sortDailyTasks puts open tasks first', () => {
    expect(sortDailyTasks([done, open]).map((t) => t.id)).toEqual([1, 2]);
    expect(sortDailyTasks([open, done]).map((t) => t.id)).toEqual([1, 2]);
  });

  test('sortDailyTasks orders same-status by created_at desc', () => {
    const older = { id: 3, is_done: false, created_at: '2026-06-01T08:00:00Z' };
    const newer = { id: 4, is_done: false, created_at: '2026-06-01T12:00:00Z' };
    expect(sortDailyTasks([older, newer])[0].id).toBe(4);
    expect(
      sortDailyTasks([
        { id: 9, is_done: true, created_at: '2026-06-01T08:00:00Z' },
        { id: 10, is_done: true, created_at: '2026-06-01T14:00:00Z' },
      ])[0].id
    ).toBe(10);
  });

  test('sortDailyTasks handles missing created_at', () => {
    expect(
      sortDailyTasks([
        { id: 5, is_done: false },
        { id: 6, is_done: false, created_at: '2026-06-01T12:00:00Z' },
      ])[0].id
    ).toBe(6);
    expect(
      sortDailyTasks([
        { id: 7, is_done: false, created_at: 'not-a-date' },
        { id: 8, is_done: false, created_at: '2026-06-01T12:00:00Z' },
      ])[0].id
    ).toBe(8);
  });

  test('countOpenTasks', () => {
    expect(countOpenTasks([open, done])).toBe(1);
    expect(countOpenTasks([])).toBe(0);
  });

  test('taskStatusLabel for open and done', () => {
    expect(taskStatusLabel(open)).toBe('To do');
    expect(taskStatusLabel(done)).toMatch(/^Done /);
    expect(taskStatusLabel({ is_done: true })).toBe('Done');
    expect(taskStatusLabel({ is_done: true, completed_at: '' })).toBe('Done');
  });

  test('formatTaskCompletedAt', () => {
    expect(formatTaskCompletedAt(null)).toBe('');
    expect(formatTaskCompletedAt('2026-06-01T12:00:00Z')).not.toBe('');
    const orig = Date.prototype.toLocaleString;
    Date.prototype.toLocaleString = () => {
      throw new Error('locale fail');
    };
    expect(formatTaskCompletedAt('not-a-real-date')).toBe('not-a-real-date');
    Date.prototype.toLocaleString = orig;
  });

  test('mergeActivityDates unions and sorts desc', () => {
    expect(mergeActivityDates(['2026-06-01'], ['2026-06-02'])).toEqual([
      '2026-06-02',
      '2026-06-01',
    ]);
    expect(mergeActivityDates(['2026-06-01'], ['2026-06-01'])).toEqual(['2026-06-01']);
    expect(mergeActivityDates(null, null)).toEqual([]);
    expect(mergeActivityDates(undefined, ['2026-06-02'])).toEqual(['2026-06-02']);
    expect(mergeActivityDates(['2026-06-03'], undefined)).toEqual(['2026-06-03']);
    expect(mergeActivityDates('ignored', 42)).toEqual([]);
  });

  test('taskStatusLabel uses formatted completion time when present', () => {
    const label = taskStatusLabel({
      is_done: true,
      completed_at: '2026-06-01T12:00:00Z',
    });
    expect(label.startsWith('Done ')).toBe(true);
    expect(label).not.toBe('Done');
  });
});
