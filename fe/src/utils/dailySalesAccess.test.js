import {
  canViewDailySales,
  canViewDailySalesFromStorage,
  dailySalesCustomerPath,
  dailySalesListPath,
  dayStandingLabel,
} from './dailySalesAccess';

jest.mock('./moduleFeatures', () => ({
  isModuleFeatureEnabled: jest.fn(() => true),
}));

import { isModuleFeatureEnabled } from './moduleFeatures';

describe('dailySalesAccess', () => {
  beforeEach(() => {
    localStorage.clear();
    isModuleFeatureEnabled.mockReturnValue(true);
  });

  it('allows super admin regardless of permission list', () => {
    expect(canViewDailySales([], { isSuperAdmin: true })).toBe(true);
  });

  it('allows users with sales.daily_sales', () => {
    expect(
      canViewDailySales([{ module: 'sales', action: 'daily_sales' }], {
        isSuperAdmin: false,
        profile: { role: 'manager' },
      })
    ).toBe(true);
  });

  it('allows cashiers who can view sales (their own day)', () => {
    expect(
      canViewDailySales([{ module: 'sales', action: 'view' }], {
        isSuperAdmin: false,
        profile: { role: 'cashier' },
      })
    ).toBe(true);
  });

  it('denies managers who only have sales.view', () => {
    expect(
      canViewDailySales([{ module: 'sales', action: 'view' }], {
        isSuperAdmin: false,
        profile: { role: 'manager' },
      })
    ).toBe(false);
  });

  it('denies when the module feature is off', () => {
    expect(
      canViewDailySales([{ module: 'sales', action: 'daily_sales' }], {
        isSuperAdmin: true,
        featureEnabled: false,
      })
    ).toBe(false);
  });

  it('denies users without sales access', () => {
    expect(
      canViewDailySales([{ module: 'pos', action: 'create' }], {
        isSuperAdmin: false,
      })
    ).toBe(false);
  });

  it('reads access from storage for manager with daily_sales grant', () => {
    localStorage.setItem(
      'permissions',
      JSON.stringify([{ module: 'sales', action: 'daily_sales', name: 'sales.daily_sales' }])
    );
    localStorage.setItem('user', JSON.stringify({ username: 'mgr' }));
    localStorage.setItem('profile', JSON.stringify({ role: 'manager' }));
    expect(canViewDailySalesFromStorage()).toBe(true);
  });

  it('hides daily sales for manager with only sales.view', () => {
    localStorage.setItem(
      'permissions',
      JSON.stringify([{ module: 'sales', action: 'view' }])
    );
    localStorage.setItem('user', JSON.stringify({ username: 'mgr' }));
    localStorage.setItem('profile', JSON.stringify({ role: 'manager' }));
    expect(canViewDailySalesFromStorage()).toBe(false);
  });

  it('allows super admin from storage without explicit permission', () => {
    localStorage.setItem('permissions', JSON.stringify([]));
    localStorage.setItem('user', JSON.stringify({ username: 'admin', is_superuser: true }));
    localStorage.setItem('profile', JSON.stringify({ role: 'super_admin' }));
    expect(canViewDailySalesFromStorage()).toBe(true);
  });

  it('hides when Module Settings feature is off', () => {
    isModuleFeatureEnabled.mockReturnValue(false);
    localStorage.setItem(
      'permissions',
      JSON.stringify([{ module: 'sales', action: 'daily_sales' }])
    );
    localStorage.setItem('user', JSON.stringify({ username: 'admin', is_superuser: true }));
    localStorage.setItem('profile', JSON.stringify({ role: 'super_admin' }));
    expect(canViewDailySalesFromStorage()).toBe(false);
  });

  it('builds customer path without date', () => {
    expect(dailySalesCustomerPath(3)).toBe('/sales/daily/customers/3');
  });

  it('builds customer and list paths with date', () => {
    expect(dailySalesCustomerPath(9, '2026-09-12')).toBe(
      '/sales/daily/customers/9?date=2026-09-12'
    );
    expect(dailySalesListPath('2026-09-12')).toBe('/sales/daily?date=2026-09-12');
    expect(dailySalesListPath()).toBe('/sales/daily');
  });

  it('labels day standing', () => {
    expect(dayStandingLabel('good')).toMatch(/Good/i);
    expect(dayStandingLabel('mixed')).toMatch(/Mixed/i);
    expect(dayStandingLabel('debt')).toMatch(/debt/i);
    expect(dayStandingLabel('x')).toMatch(/Unknown/i);
  });
});
