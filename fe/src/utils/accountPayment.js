/**
 * Debt / partial-payment helpers — collect some now, or record the full sale as debt.
 */

export function computeAccountBalanceDue(total, amountPaid) {
  const totalN = Number(total) || 0;
  const paidN = Number(amountPaid) || 0;
  return Math.max(0, Math.round((totalN - paidN) * 100) / 100);
}

export function isFullPayLater(total, amountPaid) {
  const paid = Number(amountPaid) || 0;
  return paid === 0 && (Number(total) || 0) > 0;
}

export const ACCOUNT_PAYMENT_LABEL = 'Allow debt / partial payment';
export const ACCOUNT_PAYMENT_HINT =
  'Collect part of the total now, or record the full sale as debt for this customer.';
