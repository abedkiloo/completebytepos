import {
  PERSONA,
  resolvePersona,
  hasPermission,
  canAccessRoute,
} from './roleAccess';

describe('roleAccess', () => {
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
});
