/**
 * Cashier sales and salesperson debt collections share the Approve sales desk.
 */

import { hasPermission } from './roleAccess';
import { userCanApproveSales } from './saleCompletionApproval';

export const DEBT_COLLECTION_ACTION = 'debt_collection';
export const SALE_COMPLETE_ACTION = 'sale_complete';
export const SALES_DESK_QUEUE_ACTIONS = [SALE_COMPLETE_ACTION, DEBT_COLLECTION_ACTION];

export function userCanApproveDebtCollections(permissions = []) {
  return hasPermission(permissions, 'debt_management', 'approve');
}

export function userCanOpenSaleApprovals(permissions = []) {
  return userCanApproveSales(permissions) || userCanApproveDebtCollections(permissions);
}

export function pendingDebtCollectionParams() {
  return { action_type: DEBT_COLLECTION_ACTION };
}

export function isSalesDeskQueueAction(actionType) {
  return SALES_DESK_QUEUE_ACTIONS.includes(String(actionType || ''));
}

export function otherPendingApprovalRows(pendingRows = []) {
  if (!Array.isArray(pendingRows)) return [];
  return pendingRows.filter((row) => !isSalesDeskQueueAction(row?.action_type));
}

export function collectionAmount(change) {
  return (
    change?.apply_payload?.amount ||
    change?.proposed_values?.amount ||
    ''
  );
}

export function collectionMethod(change) {
  return (
    change?.apply_payload?.payment_method ||
    change?.proposed_values?.payment_method ||
    'cash'
  );
}

export function saleApprovalsEmpty({ sales = [], collections = [] } = {}) {
  const saleCount = Array.isArray(sales) ? sales.length : 0;
  const collectionCount = Array.isArray(collections) ? collections.length : 0;
  return saleCount === 0 && collectionCount === 0;
}

export function saleApprovalsBadgeCount({ salesCount = 0, collectionsCount = 0 } = {}) {
  return (Number(salesCount) || 0) + (Number(collectionsCount) || 0);
}
