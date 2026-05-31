import {
  reportsEnableSalesReports,
  reportsShowDiscount,
  reportsShowCostAndProfit,
} from './reportDisplay';

describe('reportDisplay', () => {
  test('sales reports default on', () => {
    expect(reportsEnableSalesReports({})).toBe(true);
  });

  test('discount hidden when flag off', () => {
    expect(reportsShowDiscount({ show_discount_in_reports: false })).toBe(false);
  });

  test('profit metrics hidden when flag off', () => {
    expect(reportsShowCostAndProfit({ show_cost_and_profit: false })).toBe(false);
  });
});
