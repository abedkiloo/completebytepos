import { formatOccurredDate, toDateInputValue, toLocalISODate } from './localDate';

describe('localDate', () => {
  const kenyaMorning = new Date(2026, 8, 28, 1, 15, 0);

  it('toLocalISODate defaults to now', () => {
    expect(toLocalISODate()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('toDateInputValue defaults empty input to today', () => {
    expect(toDateInputValue()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('toLocalISODate returns empty for invalid input', () => {
    expect(toLocalISODate('not-a-date')).toBe('');
    expect(toLocalISODate(new Date('invalid'))).toBe('');
  });

  it('toDateInputValue keeps YYYY-MM-DD and strips time from ISO datetimes', () => {
    expect(toDateInputValue('2026-03-04')).toBe('2026-03-04');
    expect(toDateInputValue('2026-03-04T21:00:00.000Z')).toBe('2026-03-04');
    expect(toDateInputValue(new Date(2026, 2, 4, 18, 0, 0))).toBe('2026-03-04');
  });

  it('toDateInputValue parses non-ISO date strings', () => {
    expect(toDateInputValue('March 4, 2026')).toBe('2026-03-04');
  });

  it('toDateInputValue falls back to local today when empty or invalid', () => {
    expect(toDateInputValue('', kenyaMorning)).toBe('2026-09-28');
    expect(toDateInputValue(null, kenyaMorning)).toBe('2026-09-28');
    expect(toDateInputValue('   ', kenyaMorning)).toBe('2026-09-28');
    expect(toDateInputValue('nope', kenyaMorning)).toBe('2026-09-28');
  });

  it('toDateInputValue falls back when a Date is invalid', () => {
    expect(toDateInputValue(new Date('invalid'), kenyaMorning)).toBe('2026-09-28');
  });

  it('formatOccurredDate does not shift a date-only string', () => {
    expect(formatOccurredDate('2026-09-28')).toMatch(/28/);
    expect(formatOccurredDate('2026-09-28')).toMatch(/2026/);
    expect(formatOccurredDate('2026-09-28T00:00:00Z')).toMatch(/28/);
    expect(formatOccurredDate('')).toBe('');
    expect(formatOccurredDate(null)).toBe('');
  });
});
