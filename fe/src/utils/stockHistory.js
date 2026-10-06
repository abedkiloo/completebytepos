/**
 * Product stock history trail — mirrors debt ledger wording.
 * Previous stock 400 · Sold 45 · New stock 355 · by User K
 */
import {
  inventoryShowProductStockHistory,
  inventoryShowStockMovements,
} from './inventoryDisplay';
import { PERSONA } from './roleAccess';

export function formatStockTrail(entry) {
  if (!entry) return '';
  if (entry.stock_flow) return entry.stock_flow;

  const parts = [];
  if (entry.previous_stock != null) {
    parts.push(`Previous stock ${entry.previous_stock}`);
  }
  if (entry.change_label) {
    parts.push(entry.change_label);
  } else if (entry.change_qty != null) {
    const q = Number(entry.change_qty);
    parts.push(q >= 0 ? `Received ${q}` : `Sold ${Math.abs(q)}`);
  }
  if (entry.new_stock != null) {
    parts.push(`New stock ${entry.new_stock}`);
  }
  const who = entry.user_display || entry.user_name;
  if (who) {
    parts.push(`by ${who}`);
  }
  return parts.join(' · ');
}

export function stockHistoryMovementTone(type) {
  const map = {
    sale: 'destructive',
    purchase: 'default',
    adjustment: 'secondary',
    return: 'secondary',
    damage: 'destructive',
    transfer: 'secondary',
    waste: 'secondary',
    expired: 'secondary',
  };
  return map[type] || 'secondary';
}

/**
 * Admin-only product stock ledger (config × persona).
 * API still enforces the same gates server-side.
 */
export function canViewProductStockHistory({
  persona,
  inventorySettings,
  isAdminLike = false,
} = {}) {
  if (!inventoryShowStockMovements(inventorySettings)) return false;
  if (!inventoryShowProductStockHistory(inventorySettings)) return false;
  if (isAdminLike) return true;
  return persona === PERSONA.SUPER_ADMIN || persona === PERSONA.MANAGER;
}
