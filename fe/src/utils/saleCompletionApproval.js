/**
 * Cashier sale completion waits for a manager with sales.approve.
 */

import { hasPermission, getStoredAuth } from './roleAccess';

export const SALE_AWAITING_APPROVAL_STATUS = 'pending_approval';

export const SALE_AWAITING_APPROVAL_MESSAGE =
  'A manager will approve this sale. Stock, books, and the receipt update after they approve.';

export const SALE_APPROVED_RECEIPT_MESSAGE =
  'Sale was approved and completed. You can print the receipt.';

export function saleIsAwaitingApproval(sale) {
  return String(sale?.status || '') === SALE_AWAITING_APPROVAL_STATUS;
}

export function saleNeedsSalespersonAction(sale) {
  return Boolean(sale?.needs_salesperson_action);
}

export function saleRejectionReason(sale) {
  return String(sale?.rejection_reason || '').trim();
}

export function partitionSaleApprovalQueue(sales = []) {
  const waiting = [];
  const returned = [];
  for (const sale of Array.isArray(sales) ? sales : []) {
    if (saleNeedsSalespersonAction(sale)) {
      returned.push(sale);
    } else {
      waiting.push(sale);
    }
  }
  return { waiting, returned };
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

export function userHasAdminSaleOverride(auth = getStoredAuth()) {
  const { user, profile } = auth || {};
  if (user?.is_superuser) return true;
  if (profile?.is_super_admin) return true;
  const role = String(profile?.role || '');
  return role === 'admin' || role === 'super_admin';
}

export function userCanCorrectSaleDate(auth = getStoredAuth()) {
  const { permissions, user, profile } = auth || {};
  if (user?.is_superuser) return true;
  if (profile?.is_super_admin) return true;
  const role = String(profile?.role || '');
  if (role === 'admin' || role === 'super_admin' || role === 'manager') return true;
  return userCanApproveSales(permissions);
}

export function saleDateInputValue(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function saleMaxCorrectableDateInput() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return saleDateInputValue(d.toISOString());
}

export function saleCanAdminReturnForCorrection(sale) {
  const status = String(sale?.status || '');
  if (status === 'awaiting_payment') return true;
  if (status === 'completed') {
    return String(sale?.refund_status || 'none') === 'none';
  }
  return false;
}

export function awaitingApprovalListParams(filters = {}) {
  return { ...filters, status: SALE_AWAITING_APPROVAL_STATUS };
}
