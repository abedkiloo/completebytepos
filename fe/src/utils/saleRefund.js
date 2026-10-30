/**
 * Sale refund helpers — permissions and payload building.
 */

import { hasPermission } from './roleAccess';

/** Void/refund: Admin/Super Admin only. */
export function userCanRefundSales(permissions, { isAdmin = false } = {}) {
  if (isAdmin) return true;
  return hasPermission(permissions, 'sales', 'refund');
}

/** Admin correction — only the explicit checkbox, never inferred from manager role. */
export function userCanRollbackSales(permissions) {
  return hasPermission(permissions, 'sales', 'rollback');
}

/** Unvoid / uncancel: Admin/Super Admin only. */
export function userCanUnvoidSales(permissions, { isAdmin = false } = {}) {
  if (isAdmin) return true;
  return false;
}

export function saleIsUnvoidable(sale) {
  if (!sale) return false;
  if (sale.status === 'cancelled') return true;
  return sale.status === 'completed' && sale.refund_status === 'refunded';
}

export function saleIsRollbackable(sale) {
  if (!sale) return false;
  if (sale.can_rollback === false) return false;
  if (sale.status !== 'completed') return false;
  const status = sale.refund_status || 'none';
  return status === 'none';
}

export function saleIsRefundable(sale) {
  if (!sale) return false;
  if (sale.status !== 'completed') return false;
  if (sale.refund_status === 'refunded') return false;
  const remaining = parseFloat(sale.refundable_remaining ?? sale.total ?? 0);
  return remaining > 0;
}

export function buildFullRefundPayload(reason) {
  return { full: true, reason: String(reason || '').trim() };
}

export function buildRollbackPayload(reason) {
  return { reason: String(reason || '').trim() };
}

export function buildPartialRefundPayload(reason, items) {
  return {
    full: false,
    reason: String(reason || '').trim(),
    items: (items || []).map((row) => ({
      sale_item_id: row.sale_item_id ?? row.id,
      quantity: parseInt(row.quantity, 10) || 0,
    })),
  };
}

export function refundStatusLabel(refundStatus) {
  if (refundStatus === 'refunded') return 'Refunded';
  if (refundStatus === 'partial') return 'Partial refund';
  return null;
}

/**
 * Handle refund API response — immediate (201) vs maker-checker queue (202).
 * @returns {'applied'|'pending'}
 */
export function handleSaleRefundResponse(response, { onApplied, onPending } = {}) {
  const status = response?.status;
  const data = response?.data;
  if (status === 202) {
    onPending?.(data?.pending_change, data);
    return 'pending';
  }
  onApplied?.(data);
  return 'applied';
}
