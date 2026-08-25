/**
 * Generic pre-commit confirmation helpers (stock, refunds, payments, etc.).
 */

export function buildCommitRows(entries = []) {
  return (Array.isArray(entries) ? entries : [])
    .filter((row) => row && row.label != null && row.value != null && row.value !== '')
    .map((row) => ({
      label: String(row.label),
      value: String(row.value),
      tone: row.tone || 'default',
      emphasis: Boolean(row.emphasis),
    }));
}

export function formatSignedQty(qty) {
  const n = Number(qty) || 0;
  if (n > 0) return `+${n}`;
  return String(n);
}
