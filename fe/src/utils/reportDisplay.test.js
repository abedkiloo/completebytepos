import {
  reportsEnableSalesReports,
  reportsEnableProductReports,
  reportsLegacyReportEnabled,
  reportsProductTrendsEnabled,
  reportsShowDiscount,
  reportsShowCostAndProfit,
  userMayViewDashboardProfit,
  userMayViewDashboardRevenue,
  userMayViewProductTrends,
} from './reportDisplay';
import * as moduleFeatures from './moduleFeatures';

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

  test('product trends follow product reports setting and feature flag', () => {
    expect(reportsEnableProductReports({})).toBe(true);
    jest.spyOn(moduleFeatures, 'isModuleFeatureEnabled').mockReturnValue(true);
    expect(reportsProductTrendsEnabled({})).toBe(true);
    expect(reportsProductTrendsEnabled({ enable_product_reports: false })).toBe(false);
    moduleFeatures.isModuleFeatureEnabled.mockReturnValue(false);
    expect(reportsProductTrendsEnabled({})).toBe(false);
    moduleFeatures.isModuleFeatureEnabled.mockRestore();
  });

  test('userMayViewProductTrends needs reports.view and enabled flags', () => {
    const perms = [{ module: 'reports', action: 'view' }];
    jest.spyOn(moduleFeatures, 'isModuleFeatureEnabled').mockReturnValue(true);
    expect(userMayViewProductTrends(perms, {})).toBe(true);
    expect(userMayViewProductTrends([], {})).toBe(false);
    expect(
      userMayViewProductTrends(perms, { enable_product_reports: false })
    ).toBe(false);
    moduleFeatures.isModuleFeatureEnabled.mockRestore();
  });

  test('dashboard profit requires reports.view, the store toggle, and cost access', () => {
    const perms = [{ module: 'reports', action: 'view' }];
    expect(userMayViewDashboardProfit(perms, {})).toBe(false);
    localStorage.setItem('profile', JSON.stringify({ role: 'super_admin' }));
    expect(userMayViewDashboardProfit(perms, {})).toBe(true);
    expect(userMayViewDashboardProfit(perms, { show_cost_and_profit: false })).toBe(false);
    localStorage.removeItem('profile');
    localStorage.setItem('permissions', JSON.stringify([
      { module: 'products', action: 'view_cost' },
    ]));
    expect(userMayViewDashboardProfit(perms, {})).toBe(true);
    localStorage.removeItem('permissions');
    expect(userMayViewDashboardProfit([], {})).toBe(false);
  });
});
