/**
 * Sale refund helpers — permissions and payload building.
 */

import { hasPermission } from './roleAccess';

export function userCanRefundSales(permissions, { isManagerOrAdmin = false } = {}) {
  if (isManagerOrAdmin) return true;
  return hasPermission(permissions, 'sales', 'refund');
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
