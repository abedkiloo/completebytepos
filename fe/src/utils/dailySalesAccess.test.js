import {
  canViewDailySales,
  canViewDailySalesFromStorage,
  dailySalesCustomerPath,
  dailySalesListPath,
  dayStandingLabel,
} from './dailySalesAccess';

describe('dailySalesAccess', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('allows super admin regardless of permission list', () => {
    expect(canViewDailySales([], { isSuperAdmin: true })).toBe(true);
  });

  it('allows users with sales.daily_sales', () => {
    expect(
      canViewDailySales([{ module: 'sales', action: 'daily_sales' }], {
        isSuperAdmin: false,
      })
    ).toBe(true);
  });

  it('denies users without the permission', () => {
    expect(
      canViewDailySales([{ module: 'sales', action: 'view' }], {
        isSuperAdmin: false,
      })
    ).toBe(false);
  });

  it('reads access from storage', () => {
    localStorage.setItem(
      'permissions',
      JSON.stringify([{ module: 'sales', action: 'daily_sales', name: 'sales.daily_sales' }])
    );
    localStorage.setItem('user', JSON.stringify({ username: 'mgr' }));
    localStorage.setItem('profile', JSON.stringify({ role: 'manager' }));
    expect(canViewDailySalesFromStorage()).toBe(true);
  });

  it('allows super admin from storage without explicit permission', () => {
    localStorage.setItem('permissions', JSON.stringify([]));
    localStorage.setItem('user', JSON.stringify({ username: 'admin', is_superuser: true }));
    localStorage.setItem('profile', JSON.stringify({ role: 'super_admin' }));
    expect(canViewDailySalesFromStorage()).toBe(true);
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
