import {
  inventoryShowStockMovements,
  inventoryAdjustmentsEnabled,
  inventoryPurchasesEnabled,
  inventoryTransfersEnabled,
  inventoryShowLowStockAlerts,
  inventoryShowOutOfStockAlerts,
  inventoryReportEnabled,
  inventoryShowMovementCost,
  inventoryAllowMovementUndo,
} from './inventoryDisplay';

describe('inventoryDisplay', () => {
  test('inventory flags default on', () => {
    expect(inventoryShowStockMovements({})).toBe(true);
    expect(inventoryAdjustmentsEnabled({})).toBe(true);
    expect(inventoryPurchasesEnabled({})).toBe(true);
    expect(inventoryTransfersEnabled({})).toBe(true);
    expect(inventoryShowLowStockAlerts({})).toBe(true);
    expect(inventoryShowOutOfStockAlerts({})).toBe(true);
    expect(inventoryReportEnabled({})).toBe(true);
    expect(inventoryShowMovementCost({})).toBe(true);
    expect(inventoryAllowMovementUndo({})).toBe(true);
  });

  test('flags respect explicit false', () => {
    const off = {
      show_stock_movements: false,
      enable_stock_adjustments: false,
      enable_stock_purchases: false,
      enable_stock_transfers: false,
      show_low_stock_alerts: false,
      show_out_of_stock_alerts: false,
      enable_inventory_report: false,
      show_movement_cost: false,
      allow_movement_undo: false,
    };
    expect(inventoryShowStockMovements(off)).toBe(false);
    expect(inventoryAdjustmentsEnabled(off)).toBe(false);
    expect(inventoryPurchasesEnabled(off)).toBe(false);
    expect(inventoryTransfersEnabled(off)).toBe(false);
    expect(inventoryShowLowStockAlerts(off)).toBe(false);
    expect(inventoryShowOutOfStockAlerts(off)).toBe(false);
    expect(inventoryReportEnabled(off)).toBe(false);
    expect(inventoryShowMovementCost(off)).toBe(false);
    expect(inventoryAllowMovementUndo(off)).toBe(false);
  });
});
