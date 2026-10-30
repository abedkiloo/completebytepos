/**
 * Helpers for customer lifetime detail + debt trail display.
 */

export function formatDebtTrail(entry) {
  if (!entry) return '';
  const parts = [];
  const isCorrection = entry.source_type === 'other';
  if (entry.previous_debt != null) {
    parts.push(`Previous debt ${entry.previous_debt}`);
  }
  if (!isCorrection && entry.sale_paid != null && entry.sale_total != null) {
    parts.push(`Sale ${entry.sale_total} · paid ${entry.sale_paid}`);
  } else if (!isCorrection && entry.payment_amount != null) {
    parts.push(`Paid ${entry.payment_amount}`);
  } else if (isCorrection && entry.amount != null) {
    parts.push(`Adjustment ${entry.amount}`);
  }
  if (!isCorrection && entry.debt_added != null) {
    parts.push(`Debt added ${entry.debt_added}`);
  }
  if (entry.new_debt != null) {
    parts.push(`New debt ${entry.new_debt}`);
  }
  return parts.join(' · ');
}

/** Extra settlement meta for debt payments: method, reference, who recorded. */
export function formatSettlementMeta(entry) {
  if (!entry || entry.source_type !== 'debt_settlement') return '';
  const parts = [];
  const method = entry.payment_method_label || '';
  if (method) parts.push(method);
  const ref = (entry.reference || '').trim();
  if (ref) parts.push(`Ref ${ref}`);
  const who = (entry.created_by_name || '').trim();
  if (who) {
    parts.push(method === 'Cash' || entry.payment_method === 'cash' ? `Collected by ${who}` : `Recorded by ${who}`);
  }
  return parts.join(' · ');
}

/** True when a wallet row was invalidated by return-for-correction / clear / unvoid. */
export function isCorrectionLedgerNote(notes) {
  return /reversed|cleared|superseded|for correction/i.test(String(notes || ''));
}

export function ledgerSourceLabel(sourceType, notes = '') {
  if (sourceType === 'other') {
    return isCorrectionLedgerNote(notes) ? 'Correction' : 'Adjustment';
  }
  const labels = {
    debt: 'Sale debt',
    debt_settlement: 'Debt payment',
    payment: 'Wallet used',
    overpayment: 'Overpayment credit',
    refund: 'Refund',
    manual: 'Manual adjustment',
  };
  return labels[sourceType] || sourceType || 'Transaction';
}

/** Active debt repayment row (collections received). */
export function isDebtRepaymentRow(entry) {
  return Boolean(entry && entry.source_type === 'debt_settlement');
}

export function standingLabel(standing) {
  if (standing === 'debt') return 'Has debt';
  if (standing === 'credit') return 'Has credit';
  return 'Clear';
}

export function customerDetailPath(customerId, options = {}) {
  const id = encodeURIComponent(String(customerId));
  const params = new URLSearchParams();
  if (options.tab) params.set('tab', options.tab);
  const qs = params.toString();
  return qs ? `/customers/${id}?${qs}` : `/customers/${id}`;
}
