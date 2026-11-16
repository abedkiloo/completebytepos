/**
 * Labels and summary text for the weekly call book.
 *
 * Weekdays are Monday–Friday only (indexes 0–4). Outcomes are the three
 * marks the API accepts. Count lines never include a phone number.
 */

export const WEEKDAY_LABELS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];

export const CALL_OUTCOMES = [
  { value: 'called', label: 'Called' },
  { value: 'ask_later', label: 'Ask later' },
  { value: 'no_answer', label: 'No answer' },
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
 * Staff-facing name for a call outcome.
 *
 * @param {string} outcome `called`, `ask_later`, or `no_answer`.
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
