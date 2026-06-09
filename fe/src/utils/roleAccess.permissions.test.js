import {
  PERSONA,
  canAccessRoute,
  routesFromPermissions,
  hasAnyPermissionForModule,
} from './roleAccess';
import {
  GRANTABLE_ROUTE_MODULES,
  PERMISSION_MODULE_ROUTES,
} from './permissionRoutes';

function perm(module, action = 'view') {
  return { name: `${module}.${action}`, module, action };
}

function storePermissions(permissions) {
  localStorage.setItem('permissions', JSON.stringify(permissions));
}

describe('roleAccess — custom role permissions', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test.each(GRANTABLE_ROUTE_MODULES)(
    'sales user with %s.view can open primary route',
    (module) => {
      const route = PERMISSION_MODULE_ROUTES[module];
      storePermissions([perm(module, 'view')]);
      expect(canAccessRoute(PERSONA.SALES, route)).toBe(true);
      expect(routesFromPermissions([perm(module, 'view')])).toContain(route);
    }
  );

  test('sales without permissions cannot open invoicing or reports', () => {
    storePermissions([]);
    expect(canAccessRoute(PERSONA.SALES, '/invoices')).toBe(false);
    expect(canAccessRoute(PERSONA.SALES, '/reports')).toBe(false);
    expect(canAccessRoute(PERSONA.SALES, '/users')).toBe(false);
  });

  test('create permission also grants route access', () => {
    storePermissions([perm('invoicing', 'create')]);
    expect(canAccessRoute(PERSONA.SALES, '/invoices')).toBe(true);
  });

  test('hasAnyPermissionForModule accepts single or multiple modules', () => {
    const perms = [perm('expenses', 'view')];
    expect(hasAnyPermissionForModule(perms, 'expenses')).toBe(true);
    expect(hasAnyPermissionForModule(perms, ['accounting', 'expenses'])).toBe(true);
    expect(hasAnyPermissionForModule(perms, 'invoicing')).toBe(false);
  });

  test('manager persona still uses default route list without localStorage perms', () => {
    storePermissions([perm('invoicing', 'view')]);
    expect(canAccessRoute(PERSONA.MANAGER, '/invoices')).toBe(true);
    expect(canAccessRoute(PERSONA.MANAGER, '/users')).toBe(false);
  });
});
