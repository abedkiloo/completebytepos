const ISO_DATE_PREFIX = /^(\d{4}-\d{2}-\d{2})/;

/**
 * Calendar date in the user's local timezone as YYYY-MM-DD.
 * Avoids UTC `toISOString()` which can roll the day back in Kenya (UTC+3).
 */
export function toLocalISODate(date = new Date()) {
  const d = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(d.getTime())) return '';
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Normalize API/form values for `<input type="date">`.
 * Accepts YYYY-MM-DD, ISO datetimes, and Date objects.
 */
export function toDateInputValue(value, fallbackNow = new Date()) {
  if (value instanceof Date) {
    return toLocalISODate(value) || toLocalISODate(fallbackNow);
  }
  const text = String(value ?? '').trim();
  if (!text) return toLocalISODate(fallbackNow);
  const match = text.match(ISO_DATE_PREFIX);
  if (match) return match[1];
  const parsed = new Date(text);
  if (!Number.isNaN(parsed.getTime())) return toLocalISODate(parsed);
  return toLocalISODate(fallbackNow);
}

/** Human-readable occurred date that does not shift on timezone parse. */
export function formatOccurredDate(value) {
  const iso = String(value ?? '').trim().match(ISO_DATE_PREFIX)?.[1];
  if (!iso) return '';
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString('en-KE', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}
