import {
  reportsProductProfitabilityEnabled,
  userMayViewProductProfitability,
} from './reportDisplay';

jest.mock('./moduleFeatures', () => ({
  isModuleFeatureEnabled: jest.fn(() => true),
}));

jest.mock('./productAccess', () => ({
  userMaySeeProductCost: jest.fn(() => true),
}));

import { isModuleFeatureEnabled } from './moduleFeatures';
import { userMaySeeProductCost } from './productAccess';

describe('product profitability report gates', () => {
  beforeEach(() => {
    isModuleFeatureEnabled.mockReturnValue(true);
    userMaySeeProductCost.mockReturnValue(true);
  });

  it('requires product reports + cost toggle + feature', () => {
    expect(
      reportsProductProfitabilityEnabled({
        enable_product_reports: true,
        show_cost_and_profit: true,
      })
    ).toBe(true);
    expect(
      reportsProductProfitabilityEnabled({
        enable_product_reports: false,
        show_cost_and_profit: true,
      })
    ).toBe(false);
    isModuleFeatureEnabled.mockReturnValue(false);
    expect(
      reportsProductProfitabilityEnabled({
        enable_product_reports: true,
        show_cost_and_profit: true,
      })
    ).toBe(false);
  });

  it('viewer needs reports.view and cost access', () => {
    const perms = [{ module: 'reports', action: 'view' }];
    expect(
      userMayViewProductProfitability(perms, {
        enable_product_reports: true,
        show_cost_and_profit: true,
      })
    ).toBe(true);
    userMaySeeProductCost.mockReturnValue(false);
    expect(
      userMayViewProductProfitability(perms, {
        enable_product_reports: true,
        show_cost_and_profit: true,
      })
    ).toBe(false);
  });
});
