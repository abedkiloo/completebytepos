/**
 * Build a normalized summary for the pre-commit sale confirmation dialog.
 */
export function buildSaleCommitSummary({
  total = 0,
  received = 0,
  paymentMethod = 'cash',
  itemCount = 0,
  customerName = null,
  paymentReference = '',
} = {}) {
  const tot = Number(total) || 0;
  const paid = Number(received) || 0;
  const change = Math.max(0, paid - tot);
  const balance = Math.max(0, tot - paid);
  let kind = 'full';
  if (balance > 0 && paid === 0) kind = 'pay_later';
  else if (balance > 0) kind = 'partial';

  return {
    total: tot,
    received: paid,
    change,
    balance,
    paymentMethod: String(paymentMethod || 'cash'),
    itemCount: Number(itemCount) || 0,
    customerName: customerName || null,
    paymentReference: String(paymentReference || '').trim(),
    kind,
  };
}

export function saleCommitConfirmLabel(kind) {
  if (kind === 'pay_later') return 'Confirm — pay later';
  if (kind === 'partial') return 'Confirm sale & debt';
  return 'Confirm & complete sale';
}

export function saleCommitTitle(kind) {
  if (kind === 'pay_later') return 'Confirm pay-later sale?';
  if (kind === 'partial') return 'Confirm partial payment?';
  return 'Confirm sale?';
}
