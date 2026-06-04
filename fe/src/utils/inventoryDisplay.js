import { isModuleFlagEnabled } from './moduleSettingsCache';
import {
  inventoryAdjustmentsAllowed,
  inventoryLowStockAllowed,
  inventoryMovementsAllowed,
  inventoryPurchasesAllowed,
  inventoryReportAllowed,
  inventoryTransfersAllowed,
} from './inventoryAccess';

export function inventoryShowStockMovements(settings) {
  return inventoryMovementsAllowed(settings);
}

export function inventoryAdjustmentsEnabled(settings) {
  return inventoryAdjustmentsAllowed(settings);
}

export function inventoryPurchasesEnabled(settings) {
  return inventoryPurchasesAllowed(settings);
}

export function inventoryTransfersEnabled(settings) {
  return inventoryTransfersAllowed(settings);
}

export function inventoryShowLowStockAlerts(settings) {
  return inventoryLowStockAllowed(settings);
}

export function inventoryShowOutOfStockAlerts(settings) {
  return isModuleFlagEnabled(settings, 'show_out_of_stock_alerts', true);
}

export function inventoryReportEnabled(settings) {
  return inventoryReportAllowed(settings);
}

export function inventoryShowMovementCost(settings) {
  return isModuleFlagEnabled(settings, 'show_movement_cost', true);
}

export function inventoryAllowMovementUndo(settings) {
  return isModuleFlagEnabled(settings, 'allow_movement_undo', true);
}
