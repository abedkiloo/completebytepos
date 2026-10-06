import {
  canViewProductStockHistory,
  formatStockTrail,
} from './stockHistory';
import { PERSONA } from './roleAccess';

describe('formatStockTrail', () => {
  it('prefers stock_flow from the API', () => {
    expect(
      formatStockTrail({
        stock_flow: 'Previous stock 400 · Sold 45 · New stock 355 · by User K',
      })
    ).toBe('Previous stock 400 · Sold 45 · New stock 355 · by User K');
  });

  it('builds a debt-style trail from parts', () => {
    expect(
      formatStockTrail({
        previous_stock: 400,
        change_label: 'Sold 45',
        new_stock: 355,
        user_name: 'User K',
      })
    ).toBe('Previous stock 400 · Sold 45 · New stock 355 · by User K');
  });
});

describe('canViewProductStockHistory', () => {
  it('allows manager and super admin when config defaults on', () => {
    expect(
      canViewProductStockHistory({
        persona: PERSONA.MANAGER,
        inventorySettings: {},
      })
    ).toBe(true);
    expect(
      canViewProductStockHistory({
        persona: PERSONA.SUPER_ADMIN,
        inventorySettings: {},
      })
    ).toBe(true);
  });

  it('hides from sales persona', () => {
    expect(
      canViewProductStockHistory({
        persona: PERSONA.SALES,
        inventorySettings: {},
      })
    ).toBe(false);
  });

  it('respects config off', () => {
    expect(
      canViewProductStockHistory({
        persona: PERSONA.MANAGER,
        inventorySettings: { show_product_stock_history: false },
      })
    ).toBe(false);
  });
});
