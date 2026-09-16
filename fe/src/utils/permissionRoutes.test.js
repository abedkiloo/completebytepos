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
      'daily_notes', 'suppliers', 'employees', 'customers', 'debt_management',
      'dispatch',
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
    expect(moduleForPath('/pos/billing')).toBe('pos');
    expect(moduleForPath('/invoices/123')).toBe('invoicing');
    expect(moduleForPath('/customers/debt')).toBe('debt_management');
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

  test('routePermissionGateForPath gates daily sales tracker', () => {
    const { routePermissionGateForPath } = require('./permissionRoutes');
    expect(routePermissionGateForPath('/customers/debt')).toEqual(
      expect.objectContaining({ module: 'debt_management', action: 'view' })
    );
    expect(routePermissionGateForPath('/sales/daily')).toEqual(
      expect.objectContaining({ module: 'sales', action: 'daily_sales' })
    );
    expect(routePermissionGateForPath('/sales/daily/customers/9')).toEqual(
      expect.objectContaining({ action: 'daily_sales' })
    );
    expect(routePermissionGateForPath('/sales/field')).toEqual(
      expect.objectContaining({ module: 'dispatch', action: 'view' })
    );
    expect(routePermissionGateForPath('/sales')).toBeNull();
  });

  test('moduleForPath prefers /sales/daily over /sales', () => {
    expect(moduleForPath('/sales/daily')).toBe('sales');
    expect(moduleForPath('/sales/daily/customers/1')).toBe('sales');
  });
});
