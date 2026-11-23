/**
 * Field-load screen math. A field-load sale is stock the agent is already
 * carrying. It is not a field order.
 */

/**
 * Units still unaccounted for one product.
 *
 * @param {number} taken Units issued, 1–100000.
 * @param {number} sold Units sold from the load, 0–taken.
 * @param {number|string|null} returned Physical count, or blank before the shop counts.
 * @returns {number|null} `taken - sold - returned`, or null when no count is entered.
 */
export function missingUnits(taken, sold, returned) {
  if (returned === null || returned === undefined || returned === '') return null;
  const back = Number(returned);
  if (!Number.isFinite(back)) return null;
  return Number(taken) - Number(sold) - back;
}

/**
 * Screen status. Shortage is a pending count that does not balance.
 *
 * @param {object} load Load with `status` and `lines`.
 * @returns {string} `open`, `pending_review`, `shortage`, or `accepted`.
 */
export function displayStatus(load) {
  if (!load) return 'open';
  if (load.display_status) return load.display_status;
  if (load.status === 'accepted' || load.status === 'open') return load.status;
  const short = shortageUnits(load.lines || []);
  if (load.status === 'pending_review' && short > 0) return 'shortage';
  return load.status || 'open';
}

/**
 * Positive missing units across a load.
 *
 * @param {Array<object>} lines Load lines. Missing may be null.
 * @returns {number} 0 or more.
 */
export function shortageUnits(lines) {
  return (lines || []).reduce((sum, line) => {
    const missing = Number(line.quantity_missing);
    return sum + (Number.isFinite(missing) && missing > 0 ? missing : 0);
  }, 0);
}

/**
 * Catalog total for a field-load sale. The server prices the sale; this is the preview.
 *
 * @param {number|string} unitPrice Catalog price, 0 or more.
 * @param {number|string} quantity Whole units, 0–100000.
 * @returns {number} 2 decimal places, or 0 when the inputs are not numbers.
 */
export function saleTotal(unitPrice, quantity) {
  const total = Number(unitPrice) * Number(quantity);
  if (!Number.isFinite(total) || total < 0) return 0;
  return Math.round(total * 100) / 100;
}

/**
 * Preview total for one field-load sale that contains several products.
 *
 * @param {Array<{unitPrice: number|string, quantity: number|string}>|null} rows
 *   At most 40 rows are counted. A blank or zero quantity is left out.
 * @returns {number} Catalog total, 2 decimal places. 0 for an empty list.
 */
export function saleBasketTotal(rows) {
  if (!Array.isArray(rows)) return 0;
  return rows.slice(0, 40).reduce((sum, row) => {
    const qty = Number(row?.quantity);
    if (!Number.isFinite(qty) || qty <= 0) return sum;
    return Math.round((sum + saleTotal(row.unitPrice, qty)) * 100) / 100;
  }, 0);
}

/**
 * Whether one load belongs on the selected tab.
 *
 * `awaiting` is the approval queue: a written load, a return count, or a
 * load sent back. Shortage stays on its own tab.
 *
 * @param {object|null} load Serialized load. Null matches nothing.
 * @param {string} filter `all`, `open`, `awaiting`, `shortage`, or `accepted`.
 * @returns {boolean} True when the load should appear on that tab.
 */
export function loadMatchesFilter(load, filter) {
  if (!load) return false;
  if (!filter || filter === 'all') return true;
  const status = displayStatus(load);
  if (filter === 'awaiting') {
    return status === 'awaiting_issue' || status === 'pending_review' || status === 'issue_rejected';
  }
  return status === filter;
}

/**
 * Counts for the operations tiles, from the loads this user can see.
 *
 * @param {Array<object>} loads At most 100 serialized loads.
 * @returns {{active: number, awaitingApproval: number, shortage: number, accepted: number}}
 */
export function loadBuckets(loads) {
  const buckets = { active: 0, awaitingApproval: 0, shortage: 0, accepted: 0 };
  (loads || []).forEach((load) => {
    const status = displayStatus(load);
    if (status === 'open') buckets.active += 1;
    else if (status === 'shortage') buckets.shortage += 1;
    else if (status === 'pending_review' || status === 'awaiting_issue' || status === 'issue_rejected') {
      buckets.awaitingApproval += 1;
    }
    else if (status === 'accepted') buckets.accepted += 1;
  });
  return buckets;
}

/**
 * Staff label for a display status.
 *
 * @param {string} status `open`, `pending_review`, `shortage`, or `accepted`.
 * @returns {string} Short label.
 */
export function statusLabel(status) {
  if (status === 'open') return 'Selling in field';
  if (status === 'shortage') return 'Shortage';
  if (status === 'accepted') return 'Accepted';
  if (status === 'pending_review') return 'Return to check';
  if (status === 'awaiting_issue') return 'Waiting for manager';
  if (status === 'issue_rejected') return 'Sent back';
  return 'Open';
}
