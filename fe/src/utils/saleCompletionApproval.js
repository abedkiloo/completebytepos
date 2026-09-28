/**
 * Cashier sale completion waits for a manager with sales.approve.
 */

import { hasPermission } from './roleAccess';

export const SALE_AWAITING_APPROVAL_STATUS = 'pending_approval';

export const SALE_AWAITING_APPROVAL_MESSAGE =
  'A manager will approve this sale so you can issue the receipt.';

export const SALE_APPROVED_RECEIPT_MESSAGE =
  'Sale was approved. You can issue the receipt now.';

export function saleIsAwaitingApproval(sale) {
  return String(sale?.status || '') === SALE_AWAITING_APPROVAL_STATUS;
}

export function saleReceiptBlockedReason(sale) {
  if (saleIsAwaitingApproval(sale)) {
    return SALE_AWAITING_APPROVAL_MESSAGE;
  }
  if (sale && sale.status && sale.status !== 'completed') {
    return 'Receipt is available after the sale is completed.';
  }
  return null;
}

export function saleCheckoutSuccessToast(sale, { completedMessage = 'Sale completed' } = {}) {
  if (saleIsAwaitingApproval(sale) || sale?.pending_change) {
    return sale?.message || SALE_AWAITING_APPROVAL_MESSAGE;
  }
  return completedMessage;
}

export function userCanApproveSales(permissions = []) {
  return hasPermission(permissions, 'sales', 'approve');
}

export function awaitingApprovalListParams(filters = {}) {
  return { ...filters, status: SALE_AWAITING_APPROVAL_STATUS };
}
