import {
  REPORT_PERIODS,
  periodToDateFilters,
  datesMatchPeriod,
  detectPeriodFromDates,
} from './reportPeriods';

const fixedNow = new Date('2026-07-06T15:30:00');

describe('reportPeriods', () => {
  it('exposes today, week, month, and year presets', () => {
    expect(REPORT_PERIODS.map((p) => p.id)).toEqual(['today', 'week', 'month', 'year']);
  });

  it('maps today to a single date', () => {
    expect(periodToDateFilters('today', fixedNow)).toEqual({
      date_from: '2026-07-06',
      date_to: '2026-07-06',
    });
  });

  it('maps week to rolling 7 days', () => {
    expect(periodToDateFilters('week', fixedNow)).toEqual({
      date_from: '2026-06-30',
      date_to: '2026-07-06',
    });
  });

  it('maps month to calendar month start through today', () => {
    expect(periodToDateFilters('month', fixedNow)).toEqual({
      date_from: '2026-07-01',
      date_to: '2026-07-06',
    });
  });

  it('maps year to Jan 1 through today', () => {
    expect(periodToDateFilters('year', fixedNow)).toEqual({
      date_from: '2026-01-01',
      date_to: '2026-07-06',
    });
  });

  it('detects matching preset from date filters', () => {
    const { date_from, date_to } = periodToDateFilters('month', fixedNow);
    expect(detectPeriodFromDates(date_from, date_to, fixedNow)).toBe('month');
    expect(detectPeriodFromDates('2026-01-01', '2026-01-15', fixedNow)).toBe('custom');
    expect(datesMatchPeriod(date_from, date_to, 'month', fixedNow)).toBe(true);
  });
});
