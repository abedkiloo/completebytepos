/** Labels and helpers for Debt Management UI. */

export const AGING_BUCKET_OPTIONS = [
  { id: '', name: 'All ages' },
  { id: '0_7', name: '0–7 days' },
  { id: '8_30', name: '8–30 days' },
  { id: '31_60', name: '31–60 days' },
  { id: '60_plus', name: '60+ days' },
];

export const AGING_BUCKET_LABELS = {
  '0_7': '0–7 days',
  '8_30': '8–30 days',
  '31_60': '31–60 days',
  '60_plus': '60+ days',
};

export function emptyDebtSummary() {
  return {
    customers_with_debt: 0,
    total_debt: '0.00',
    average_debt: '0.00',
    collected_today: '0.00',
    aging: {
      '0_7': { count: 0, amount: '0.00' },
      '8_30': { count: 0, amount: '0.00' },
      '31_60': { count: 0, amount: '0.00' },
      '60_plus': { count: 0, amount: '0.00' },
    },
  };
}

export function emptyDebtCollections() {
  return {
    date: '',
    count: 0,
    total: '0.00',
    results: [],
  };
}

/** Local calendar date as YYYY-MM-DD (not UTC). */
export function getTodayDateString() {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function shiftDate(dateStr, offsetDays) {
  if (!dateStr) return getTodayDateString();
  const [y, m, d] = dateStr.split('-').map(Number);
  const dateObj = new Date(y, m - 1, d);
  dateObj.setDate(dateObj.getDate() + offsetDays);
  const ry = dateObj.getFullYear();
  const rm = String(dateObj.getMonth() + 1).padStart(2, '0');
  const rd = String(dateObj.getDate()).padStart(2, '0');
  return `${ry}-${rm}-${rd}`;
}

export function formatDateLabel(dateStr) {
  if (!dateStr) return '';
  const todayStr = getTodayDateString();
  const yesterdayStr = shiftDate(todayStr, -1);
  const [y, m, d] = dateStr.split('-').map(Number);
  const dateObj = new Date(y, m - 1, d);
  const formatted = dateObj.toLocaleDateString(undefined, {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
  if (dateStr === todayStr) {
    return `Today · ${formatted}`;
  }
  if (dateStr === yesterdayStr) {
    return `Yesterday · ${formatted}`;
  }
  return formatted;
}

export function walletTxnLabel(sourceType) {
  switch (sourceType) {
    case 'debt':
      return 'Debt added';
    case 'debt_settlement':
      return 'Payment received';
    case 'refund':
      return 'Refund';
    case 'overpayment':
      return 'Overpayment credit';
    case 'payment':
      return 'Wallet payment';
    case 'manual':
      return 'Manual adjustment';
    default:
      return sourceType || 'Transaction';
  }
}
