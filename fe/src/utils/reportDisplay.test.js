import {
  reportsEnableSalesReports,
  reportsLegacyReportEnabled,
  reportsShowDiscount,
  reportsShowCostAndProfit,
  userMayViewDashboardProfit,
  userMayViewDashboardRevenue,
} from './reportDisplay';

describe('reportDisplay', () => {
  test('sales reports default on', () => {
    expect(reportsEnableSalesReports({})).toBe(true);
  });

  test('stock-valuation follows inventory reports toggle', () => {
    expect(reportsLegacyReportEnabled({}, 'stock-valuation')).toBe(true);
    expect(
      reportsLegacyReportEnabled({ enable_inventory_reports: false }, 'stock-valuation')
    ).toBe(false);
  });

  test('discount hidden when flag off', () => {
    expect(reportsShowDiscount({ show_discount_in_reports: false })).toBe(false);
  });

  test('profit metrics hidden when flag off', () => {
    expect(reportsShowCostAndProfit({ show_cost_and_profit: false })).toBe(false);
  });

  test('dashboard revenue requires reports.view', () => {
    const perms = [{ module: 'reports', action: 'view' }];
    expect(userMayViewDashboardRevenue(perms)).toBe(true);
    expect(userMayViewDashboardRevenue([])).toBe(false);
  });

  test('dashboard profit requires reports.view and store toggle', () => {
    const perms = [{ module: 'reports', action: 'view' }];
    expect(userMayViewDashboardProfit(perms, {})).toBe(true);
    expect(userMayViewDashboardProfit(perms, { show_cost_and_profit: false })).toBe(false);
    expect(userMayViewDashboardProfit([], {})).toBe(false);
  });
});
