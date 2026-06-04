import {
  inventoryAdjustmentsAllowed,
  inventoryPurchasesAllowed,
} from './inventoryAccess';

describe('inventoryAccess dual gates', () => {
  const base = {
    inventory: {
      is_enabled: true,
      settings: {
        enable_stock_adjustments: true,
        enable_stock_purchases: true,
      },
    },
    stock: {
      is_enabled: true,
      features: { stock_adjustments: true },
    },
  };

  test('adjustments require checkbox and catalog feature', () => {
    expect(inventoryAdjustmentsAllowed(base)).toBe(true);
    expect(
      inventoryAdjustmentsAllowed({
        enable_stock_adjustments: false,
        ...base,
      })
    ).toBe(false);
    expect(
      inventoryAdjustmentsAllowed({
        enable_stock_adjustments: true,
        ...base,
        stock: { ...base.stock, features: { stock_adjustments: false } },
        inventory: {
          ...base.inventory,
          features: { stock_adjustments: false },
        },
      })
    ).toBe(false);
  });

  test('purchases require purchases flag and stock feature', () => {
    expect(inventoryPurchasesAllowed(base)).toBe(true);
    expect(
      inventoryPurchasesAllowed({ enable_stock_purchases: false, ...base })
    ).toBe(false);
    const noStockFeatures = {
      enable_stock_purchases: true,
      inventory: { is_enabled: true, features: { stock_adjustments: false } },
      stock: {
        is_enabled: true,
        features: { stock_adjustments: false, manage_stock: false },
      },
    };
    expect(inventoryPurchasesAllowed(noStockFeatures)).toBe(false);
  });
});
