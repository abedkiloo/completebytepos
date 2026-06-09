import {
  ROUTE_MODULE_MAP,
  PERMISSION_MODULE_ROUTES,
  NAV_SECTION_MODULES,
  GRANTABLE_ROUTE_MODULES,
  SUPER_ADMIN_ONLY_ROUTE_PREFIXES,
  routesFromPermissionList,
  moduleForPath,
  navSectionGrantedByPermissions,
} from './permissionRoutes';

describe('permissionRoutes registry', () => {
  test('every grantable module maps to a real app route', () => {
    const appPaths = new Set(Object.keys(ROUTE_MODULE_MAP));
    for (const [module, prefix] of Object.entries(PERMISSION_MODULE_ROUTES)) {
      const routeExists =
        appPaths.has(prefix) ||
        Object.values(ROUTE_MODULE_MAP).includes(module) ||
        (module === 'pos' && appPaths.has('/pos'));
      expect(routeExists).toBe(true);
    }
  });

  test('grantable modules list stays in sync with permission module routes', () => {
    expect(GRANTABLE_ROUTE_MODULES.sort()).toEqual(
      Object.keys(PERMISSION_MODULE_ROUTES).sort()
    );
  });

  test('backend permission modules with UI are registered (sync with test_permission_matrix.py)', () => {
    const backendUiModules = [
      'invoicing', 'sales', 'pos', 'reports', 'products', 'categories',
      'inventory', 'barcodes', 'expenses', 'income', 'accounting',
      'daily_notes', 'suppliers', 'employees', 'customers',
    ];
    for (const mod of backendUiModules) {
      expect(PERMISSION_MODULE_ROUTES[mod]).toBeTruthy();
    }
  });

  test('super-admin routes are never granted via permissions alone', () => {
    const settingsPerms = [
      { module: 'settings', action: 'view', name: 'settings.view' },
      { module: 'users', action: 'view', name: 'users.view' },
      { module: 'roles', action: 'view', name: 'roles.view' },
      { module: 'modules', action: 'view', name: 'modules.view' },
    ];
    const routes = routesFromPermissionList(settingsPerms);
    for (const blocked of SUPER_ADMIN_ONLY_ROUTE_PREFIXES) {
      expect(routes).not.toContain(blocked);
    }
  });

  test('routesFromPermissionList unlocks invoicing and reports for sales roles', () => {
    const perms = [
      { module: 'invoicing', action: 'view', name: 'invoicing.view' },
      { module: 'reports', action: 'view', name: 'reports.view' },
    ];
    expect(routesFromPermissionList(perms).sort()).toEqual(['/invoices', '/reports']);
  });

  test('moduleForPath resolves longest matching prefix', () => {
    expect(moduleForPath('/pos/billing')).toBe('sales');
    expect(moduleForPath('/invoices/123')).toBe('invoicing');
    expect(moduleForPath('/unknown')).toBeNull();
  });

  test('nav sections align with permission modules', () => {
    for (const modules of Object.values(NAV_SECTION_MODULES)) {
      const list = Array.isArray(modules) ? modules : [modules];
      for (const mod of list) {
        expect(
          Object.prototype.hasOwnProperty.call(PERMISSION_MODULE_ROUTES, mod) ||
            Object.values(ROUTE_MODULE_MAP).includes(mod)
        ).toBe(true);
      }
    }
  });

  test('navSectionGrantedByPermissions respects module lists', () => {
    const perms = [{ module: 'expenses', action: 'view' }];
    expect(navSectionGrantedByPermissions('accounting', perms)).toBe(true);
    expect(navSectionGrantedByPermissions('invoicing', perms)).toBe(false);
  });
});
