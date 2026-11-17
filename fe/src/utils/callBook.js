/**
 * Labels and summary text for the weekly call book.
 *
 * Weekdays are Monday–Friday only (indexes 0–4). Outcomes are the four
 * marks the API accepts. Count lines never include a phone number.
 * The screen copies a number. It does not place the call.
 */

export const WEEKDAY_LABELS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];

export const CALL_OUTCOMES = [
  { value: 'called', label: 'Called', tone: 'success' },
  { value: 'ask_later', label: 'Call later', tone: 'warning' },
  { value: 'no_answer', label: 'No answer', tone: 'outline' },
  { value: 'unreachable', label: 'Unreachable', tone: 'destructive' },
];

/**
 * Monday–Friday name for a weekday index.
 *
 * @param {number} index Weekday 0–4. Anything else returns an empty string.
 * @returns {string} Label, at most 9 characters.
 */
export function weekdayLabel(index) {
  if (index < 0 || index > 4) return '';
  return WEEKDAY_LABELS[index] || '';
}

/**
 * Sub-counties shown on one day's header.
 *
 * @param {object} day Day row from the book summary.
 * @param {number} [limit] Names to show, 1–40. Extra names become a count.
 * @returns {string} Comma-separated names, or an empty string.
 */
export function daySubCountyLabel(day, limit = 4) {
  const names = Array.isArray(day?.sub_counties)
    ? day.sub_counties.map((name) => String(name || '').trim()).filter(Boolean).slice(0, 40)
    : [];
  const cap = Math.min(40, Math.max(1, Number(limit) || 4));
  const shown = names.slice(0, cap);
  if (!shown.length) return '';
  const extra = names.length - shown.length;
  return extra > 0 ? `${shown.join(', ')} +${extra} more` : shown.join(', ');
}

/**
 * Staff-facing name for a call outcome.
 *
 * @param {string} outcome `called`, `ask_later`, `no_answer`, or `unreachable`.
 * @returns {string} Short label, or an empty string when unknown.
 */
export function outcomeLabel(outcome) {
  const match = CALL_OUTCOMES.find((item) => item.value === outcome);
  return match ? match.label : '';
}

/**
 * Coverage sentence for the book header.
 *
 * @param {object|null} summary API summary with called, callable, cannot_call.
 * @returns {string} One sentence. Empty when summary is missing. No phone.
 */
export function callBookCountLine(summary) {
  if (!summary) return '';
  const called = Number(summary.called) || 0;
  const callable = Number(summary.callable) || 0;
  const cannot = Number(summary.cannot_call) || 0;
  return `Called ${called} of ${callable}. ${cannot} cannot be called.`;
}

/**
 * Share of the week already recorded, as a whole percent.
 *
 * @param {number} called Customers with a result this week. 0 or more.
 * @param {number} callable Customers with a usable number. 0 or more.
 * @returns {number} 0–100. Zero when there is nobody to call.
 */
export function callCoveragePercent(called, callable) {
  const done = Number(called) || 0;
  const total = Number(callable) || 0;
  if (total <= 0 || done <= 0) return 0;
  return Math.min(100, Math.round((done / total) * 100));
}

/**
 * Short customer type for the call workspace.
 *
 * @param {string} segment Buyer segment from the book row.
 * @returns {string} At most 20 characters. Never a phone number.
 */
export function customerCategoryLabel(segment) {
  if (segment === 'dormant') return 'Dormant';
  if (segment === 'at_risk') return 'Cooling off';
  if (!segment || segment === 'none') return 'Not yet a buyer';
  return 'Existing customer';
}
