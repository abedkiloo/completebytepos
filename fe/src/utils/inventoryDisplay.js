import { isModuleFlagEnabled } from './moduleSettingsCache';

export function inventoryShowStockMovements(settings) {
  return isModuleFlagEnabled(settings, 'show_stock_movements', true);
}

export function inventoryAdjustmentsEnabled(settings) {
  return isModuleFlagEnabled(settings, 'enable_stock_adjustments', true);
}

export function inventoryPurchasesEnabled(settings) {
  return isModuleFlagEnabled(settings, 'enable_stock_purchases', true);
}

export function inventoryTransfersEnabled(settings) {
  return isModuleFlagEnabled(settings, 'enable_stock_transfers', true);
}

export function inventoryShowLowStockAlerts(settings) {
  return isModuleFlagEnabled(settings, 'show_low_stock_alerts', true);
}

export function inventoryShowOutOfStockAlerts(settings) {
  return isModuleFlagEnabled(settings, 'show_out_of_stock_alerts', true);
}

export function inventoryReportEnabled(settings) {
  return isModuleFlagEnabled(settings, 'enable_inventory_report', true);
}

export function inventoryShowMovementCost(settings) {
  return isModuleFlagEnabled(settings, 'show_movement_cost', true);
}

export function inventoryAllowMovementUndo(settings) {
  return isModuleFlagEnabled(settings, 'allow_movement_undo', true);
}
