/** Date presets for reports — mirrors backend ``resolve_period()`` in be/reports/services.py */

export const REPORT_PERIODS = [
  { id: 'today', label: 'Today' },
  { id: 'week', label: 'This week' },
  { id: 'month', label: 'This month' },
  { id: 'year', label: 'This year' },
];

export const DEFAULT_REPORT_PERIOD = 'month';

export function formatDateForApi(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/** Map a period id to ``date_from`` / ``date_to`` strings (YYYY-MM-DD). */
export function periodToDateFilters(periodId, now = new Date()) {
  const today = new Date(now);
  today.setHours(0, 0, 0, 0);
  const dateTo = formatDateForApi(today);

  switch (periodId) {
    case 'today':
      return { date_from: dateTo, date_to: dateTo };
    case 'week': {
      const start = new Date(today);
      start.setDate(start.getDate() - 6);
      return { date_from: formatDateForApi(start), date_to: dateTo };
    }
    case 'month':
      return {
        date_from: formatDateForApi(new Date(today.getFullYear(), today.getMonth(), 1)),
        date_to: dateTo,
      };
    case 'year':
      return {
        date_from: formatDateForApi(new Date(today.getFullYear(), 0, 1)),
        date_to: dateTo,
      };
    default:
      return { date_from: '', date_to: '' };
  }
}

export function datesMatchPeriod(dateFrom, dateTo, periodId, now = new Date()) {
  if (!periodId || periodId === 'custom') return false;
  const expected = periodToDateFilters(periodId, now);
  return expected.date_from === dateFrom && expected.date_to === dateTo;
}

export function detectPeriodFromDates(dateFrom, dateTo, now = new Date()) {
  for (const period of REPORT_PERIODS) {
    if (datesMatchPeriod(dateFrom, dateTo, period.id, now)) {
      return period.id;
    }
  }
  return 'custom';
}
