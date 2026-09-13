/**
 * Helpers for customer lifetime detail + debt trail display.
 */

export function formatDebtTrail(entry) {
  if (!entry) return '';
  const parts = [];
  if (entry.previous_debt != null) {
    parts.push(`Previous debt ${entry.previous_debt}`);
  }
  if (entry.sale_paid != null && entry.sale_total != null) {
    parts.push(`Sale ${entry.sale_total} · paid ${entry.sale_paid}`);
  } else if (entry.payment_amount != null) {
    parts.push(`Paid ${entry.payment_amount}`);
  }
  if (entry.debt_added != null) {
    parts.push(`Debt added ${entry.debt_added}`);
  }
  if (entry.new_debt != null) {
    parts.push(`New debt ${entry.new_debt}`);
  }
  return parts.join(' · ');
}

export function ledgerSourceLabel(sourceType) {
  const labels = {
    debt: 'Sale debt',
    debt_settlement: 'Debt payment',
    payment: 'Wallet used',
    overpayment: 'Overpayment credit',
    refund: 'Refund',
    manual: 'Manual adjustment',
    other: 'Other',
  };
  return labels[sourceType] || sourceType || 'Transaction';
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
