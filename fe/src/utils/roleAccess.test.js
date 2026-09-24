import {
  PERSONA,
  resolvePersona,
  hasPermission,
  canAccessRoute,
  isManagerOrAdminFromStorage,
  userSeesAllSalesFromStorage,
  userMayViewDeliveryHistory,
} from './roleAccess';
import { cacheModuleSettings } from './moduleSettingsCache';
import { cacheStoreSettings } from './storeSettingsCache';

describe('roleAccess', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(
      'permissions',
      JSON.stringify([
        { module: 'pos', action: 'view', name: 'pos.view' },
        { module: 'reports', action: 'view', name: 'reports.view' },
        { module: 'products', action: 'view', name: 'products.view' },
        { module: 'categories', action: 'view', name: 'categories.view' },
        { module: 'daily_notes', action: 'view', name: 'daily_notes.view' },
      ])
    );
  });

  test('resolvePersona detects super admin', () => {
    expect(
      resolvePersona({
        is_super_admin: true,
        profile: { role: 'super_admin', custom_role: { name: 'Super Admin' } },
      })
    ).toBe(PERSONA.SUPER_ADMIN);
  });

  test('resolvePersona detects manager', () => {
    expect(
      resolvePersona({
        profile: { role: 'manager', custom_role: { name: 'Manager' } },
      })
    ).toBe(PERSONA.MANAGER);
  });

  test('resolvePersona defaults to sales', () => {
    expect(
      resolvePersona({
        profile: { role: 'cashier', custom_role: { name: 'Sales Personnel' } },
      })
    ).toBe(PERSONA.SALES);
  });

  test('hasPermission matches module.action', () => {
    const perms = [{ name: 'pos.create', module: 'pos', action: 'create' }];
    expect(hasPermission(perms, 'pos', 'create')).toBe(true);
    expect(hasPermission(perms, 'reports', 'view')).toBe(false);
  });

  test('canAccessRoute for sales blocks users admin', () => {
    expect(canAccessRoute(PERSONA.SALES, '/pos')).toBe(true);
    expect(canAccessRoute(PERSONA.SALES, '/change-password')).toBe(true);
    expect(canAccessRoute(PERSONA.SALES, '/users')).toBe(false);
    expect(canAccessRoute(PERSONA.MANAGER, '/reports')).toBe(true);
  });

  test('daily sales route requires sales.daily_sales for managers', () => {
    localStorage.setItem(
      'permissions',
      JSON.stringify([{ module: 'sales', action: 'view', name: 'sales.view' }])
    );
    expect(canAccessRoute(PERSONA.MANAGER, '/sales/daily')).toBe(false);
    expect(canAccessRoute(PERSONA.MANAGER, '/sales/daily/customers/1')).toBe(false);

    localStorage.setItem(
      'permissions',
      JSON.stringify([
        { module: 'sales', action: 'view', name: 'sales.view' },
        { module: 'sales', action: 'daily_sales', name: 'sales.daily_sales' },
      ])
    );
    expect(canAccessRoute(PERSONA.MANAGER, '/sales/daily')).toBe(true);
    expect(canAccessRoute(PERSONA.MANAGER, '/sales/daily/customers/1')).toBe(true);
  });

  test('super admin can access all app modules', () => {
    const paths = [
      '/categories',
      '/customers',
      '/invoices',
      '/roles',
      '/suppliers',
      '/inventory',
      '/barcodes',
      '/accounting',
      '/module-settings',
    ];
    paths.forEach((path) => {
      expect(canAccessRoute(PERSONA.SUPER_ADMIN, path, { isSuperAdmin: true })).toBe(true);
    });
  });

  test('manager cannot open super-admin-only routes', () => {
    expect(canAccessRoute(PERSONA.MANAGER, '/categories')).toBe(true);
    expect(canAccessRoute(PERSONA.MANAGER, '/module-settings')).toBe(false);
    expect(canAccessRoute(PERSONA.MANAGER, '/users')).toBe(false);
  });

  test('resolvePersona treats django superuser as super admin', () => {
    expect(
      resolvePersona({
        user: { is_superuser: true },
        profile: { role: 'cashier' },
      })
    ).toBe(PERSONA.SUPER_ADMIN);
  });

  test('sales can access daily notes when module allows sales access', () => {
    cacheModuleSettings('daily_notes', { allow_sales_access: true });
    expect(canAccessRoute(PERSONA.SALES, '/daily-notes')).toBe(true);
  });

  test('sales can access products when store setting allows catalog add', () => {
    cacheStoreSettings({ allow_sales_add_products: true });
    expect(canAccessRoute(PERSONA.SALES, '/products')).toBe(true);
    expect(canAccessRoute(PERSONA.SALES, '/categories')).toBe(true);
    expect(canAccessRoute(PERSONA.SALES, '/product-attributes')).toBe(true);
  });

  test('sales cannot access products when catalog add is off', () => {
    cacheStoreSettings({ allow_sales_add_products: false });
    localStorage.setItem(
      'permissions',
      JSON.stringify([{ module: 'pos', action: 'view', name: 'pos.view' }])
    );
    expect(canAccessRoute(PERSONA.SALES, '/products')).toBe(false);
    expect(canAccessRoute(PERSONA.SALES, '/categories')).toBe(false);
    expect(canAccessRoute(PERSONA.SALES, '/product-attributes')).toBe(false);
  });

  test('sales can access products with default store settings cache', () => {
    expect(canAccessRoute(PERSONA.SALES, '/products')).toBe(true);
  });

  test('isManagerOrAdminFromStorage distinguishes sales from manager', () => {
    localStorage.setItem('user', JSON.stringify({ username: 'sales' }));
    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'cashier', custom_role: { name: 'Sales Personnel' } })
    );
    expect(isManagerOrAdminFromStorage()).toBe(false);

    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'manager', custom_role: { name: 'Manager' } })
    );
    expect(isManagerOrAdminFromStorage()).toBe(true);
  });

  test('userSeesAllSalesFromStorage is admin or sales.view_all only', () => {
    localStorage.setItem('user', JSON.stringify({ id: 1, username: 'mgr' }));
    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'manager', custom_role: { name: 'Manager' } })
    );
    localStorage.setItem('permissions', JSON.stringify([]));
    expect(userSeesAllSalesFromStorage()).toBe(false);

    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'admin', custom_role: { name: 'Admin' } })
    );
    expect(userSeesAllSalesFromStorage()).toBe(true);

    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'manager', custom_role: { name: 'Manager' } })
    );
    localStorage.setItem(
      'permissions',
      JSON.stringify([{ module: 'sales', action: 'view_all', name: 'sales.view_all' }])
    );
    expect(userSeesAllSalesFromStorage()).toBe(true);
  });

  test('userMayViewDeliveryHistory is manager/admin or delivery.history', () => {
    localStorage.setItem('user', JSON.stringify({ id: 1, username: 'disp' }));
    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'manager', custom_role: { name: 'Dispatcher' } })
    );
    localStorage.setItem('permissions', JSON.stringify([]));
    expect(userMayViewDeliveryHistory()).toBe(false);

    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'manager', custom_role: { name: 'Manager' } })
    );
    expect(userMayViewDeliveryHistory()).toBe(true);

    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'cashier', custom_role: { name: 'Ops' } })
    );
    expect(userMayViewDeliveryHistory()).toBe(false);
    localStorage.setItem(
      'permissions',
      JSON.stringify([{ module: 'delivery', action: 'history', name: 'delivery.history' }])
    );
    expect(userMayViewDeliveryHistory()).toBe(true);

    localStorage.setItem('user', JSON.stringify({ is_superuser: true }));
    localStorage.setItem('permissions', JSON.stringify([]));
    expect(userMayViewDeliveryHistory()).toBe(true);

    expect(
      userMayViewDeliveryHistory({
        user: { is_superuser: false },
        profile: { role: 'admin', custom_role: { name: 'Clerk' } },
        permissions: [],
      })
    ).toBe(true);
  });

  test('system-settings is super-admin only', () => {
    expect(canAccessRoute(PERSONA.SUPER_ADMIN, '/system-settings', { isSuperAdmin: true })).toBe(
      true
    );
    expect(canAccessRoute(PERSONA.MANAGER, '/system-settings')).toBe(false);
    expect(canAccessRoute(PERSONA.SALES, '/system-settings')).toBe(false);
  });

  test('sales can access invoices when role grants invoicing permissions', () => {
    localStorage.setItem(
      'permissions',
      JSON.stringify([
        { name: 'invoicing.view', module: 'invoicing', action: 'view' },
        { name: 'invoicing.create', module: 'invoicing', action: 'create' },
      ])
    );
    expect(canAccessRoute(PERSONA.SALES, '/invoices')).toBe(true);
  });

  test('sales cannot access invoices without invoicing permissions', () => {
    localStorage.setItem('permissions', JSON.stringify([]));
    expect(canAccessRoute(PERSONA.SALES, '/invoices')).toBe(false);
  });
});
