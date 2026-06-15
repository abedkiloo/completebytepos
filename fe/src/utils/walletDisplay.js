import { formatCurrency } from './formatters';

export function parseWalletBalance(balance) {
  const value = parseFloat(balance);
  return Number.isFinite(value) ? value : 0;
}

/** Amount the customer owes from negative wallet balance (POS partial-payment debt). */
export function getWalletDebtAmount(balance) {
  const value = parseWalletBalance(balance);
  return value < 0 ? Math.abs(value) : 0;
}

export function getWalletCreditAmount(balance) {
  const value = parseWalletBalance(balance);
  return value > 0 ? value : 0;
}

export function formatWalletBalanceLabel(balance) {
  const value = parseWalletBalance(balance);
  if (value < 0) return `${formatCurrency(Math.abs(value))} owed`;
  if (value > 0) return `${formatCurrency(value)} credit`;
  return formatCurrency(0);
}

export function walletBalanceTone(balance) {
  const value = parseWalletBalance(balance);
  if (value < 0) return 'debt';
  if (value > 0) return 'credit';
  return 'neutral';
}
