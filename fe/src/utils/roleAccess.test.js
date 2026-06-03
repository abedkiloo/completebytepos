import {
  PERSONA,
  resolvePersona,
  hasPermission,
  canAccessRoute,
  isManagerOrAdminFromStorage,
} from './roleAccess';
import { cacheStoreSettings } from './storeSettingsCache';

describe('roleAccess', () => {
  beforeEach(() => {
    localStorage.clear();
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
    expect(canAccessRoute(PERSONA.SALES, '/users')).toBe(false);
    expect(canAccessRoute(PERSONA.MANAGER, '/reports')).toBe(true);
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

  test('sales can access products when store setting allows catalog add', () => {
    cacheStoreSettings({ allow_sales_add_products: true });
    expect(canAccessRoute(PERSONA.SALES, '/products')).toBe(true);
    expect(canAccessRoute(PERSONA.SALES, '/categories')).toBe(true);
    expect(canAccessRoute(PERSONA.SALES, '/product-attributes')).toBe(true);
  });

  test('sales cannot access products when catalog add is off', () => {
    cacheStoreSettings({ allow_sales_add_products: false });
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

  test('system-settings is super-admin only', () => {
    expect(canAccessRoute(PERSONA.SUPER_ADMIN, '/system-settings', { isSuperAdmin: true })).toBe(
      true
    );
    expect(canAccessRoute(PERSONA.MANAGER, '/system-settings')).toBe(false);
    expect(canAccessRoute(PERSONA.SALES, '/system-settings')).toBe(false);
  });
});
