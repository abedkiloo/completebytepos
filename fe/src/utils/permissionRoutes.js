/**
 * Single source of truth: backend permission modules ↔ app routes ↔ nav sections.
 *
 * When adding a new permission module with UI:
 * 1. Add route(s) to ROUTE_MODULE_MAP
 * 2. Add PERMISSION_MODULE_ROUTES entry (primary prefix for role grants)
 * 3. If sales may access via edited roles, add NAV_SECTION_MODULES when applicable
 * 4. Extend GRANTABLE_ROUTE_MODULES tests — they will fail if step 2 is missing
 */

/** Longest-prefix wins when resolving pathname → module (see roleAccess). */
export const ROUTE_MODULE_MAP = {
  '/products': 'products',
  '/categories': 'categories',
  '/product-attributes': 'products',
  '/barcodes': 'barcodes',
  '/inventory': 'inventory',
  '/suppliers': 'suppliers',
  '/employees': 'employees',
  '/daily-notes': 'daily_notes',
  '/pos/billing': 'pos',
  '/pos': 'pos',
  '/normal-sale': 'sales',
  '/sales/daily': 'sales',
  '/sales/field': 'sales',
  '/sales': 'sales',
  '/customers/debt': 'debt_management',
  '/customers': 'customers',
  '/invoices': 'invoicing',
  '/reports': 'reports',
  '/audit-log': 'reports',
  '/pending-approvals': 'reports',
  '/accounting': 'accounting',
  '/expenses': 'expenses',
  '/expenses/categories': 'expenses',
  '/income': 'income',
  '/users': 'users',
  '/roles': 'roles',
  '/module-settings': 'modules',
  '/branches': 'settings',
  '/system-settings': 'settings',
};

/**
 * When a role has any permission on a module, sales users may open this route prefix.
 * `pos` is separate from `sales` in the permission matrix.
 */
export const PERMISSION_MODULE_ROUTES = {
  invoicing: '/invoices',
  sales: '/sales',
  pos: '/pos',
  reports: '/reports',
  products: '/products',
  categories: '/categories',
  inventory: '/inventory',
  barcodes: '/barcodes',
  expenses: '/expenses',
  income: '/income',
  accounting: '/accounting',
  daily_notes: '/daily-notes',
  suppliers: '/suppliers',
  employees: '/employees',
  customers: '/customers',
  debt_management: '/customers/debt',
  dispatch: '/sales/field',
};

/** Nav sections sales may see when their role grants module permissions. */
export const NAV_SECTION_MODULES = {
  invoicing: 'invoicing',
  reports: 'reports',
  accounting: ['accounting', 'expenses', 'income'],
  stock: 'inventory',
  suppliers: 'suppliers',
  employees: 'employees',
  inventory: ['products', 'categories', 'barcodes'],
};

/** Path prefixes that need a specific permission action (beyond module enablement). */
export const ROUTE_PERMISSION_GATES = [
  { prefix: '/customers/debt', module: 'debt_management', action: 'view' },
  { prefix: '/normal-sale', module: 'sales', action: 'create' },
  { prefix: '/sales/daily', module: 'sales', action: 'daily_sales' },
  { prefix: '/sales/field', module: 'dispatch', action: 'view' },
];

export function routePermissionGateForPath(pathname, gates = ROUTE_PERMISSION_GATES) {
  const match = [...gates]
    .sort((a, b) => b.prefix.length - a.prefix.length)
    .find((g) => pathname === g.prefix || pathname.startsWith(`${g.prefix}/`));
  return match || null;
}

/** Modules that should unlock a route when granted to a custom/edited role. */
export const GRANTABLE_ROUTE_MODULES = Object.keys(PERMISSION_MODULE_ROUTES);

/** Routes that must never be opened via permission grants alone (super-admin only). */
export const SUPER_ADMIN_ONLY_ROUTE_PREFIXES = [
  '/users',
  '/roles',
  '/module-settings',
  '/system-settings',
  '/branches',
];

export function routesFromPermissionList(
  permissions,
  moduleRoutes = PERMISSION_MODULE_ROUTES,
  superAdminOnly = SUPER_ADMIN_ONLY_ROUTE_PREFIXES
) {
  if (!Array.isArray(permissions)) return [];
  const blocked = new Set(superAdminOnly);
  const routes = new Set();
  for (const perm of permissions) {
    const prefix = moduleRoutes[perm.module];
    if (prefix && !blocked.has(prefix)) {
      routes.add(prefix);
    }
  }
  return [...routes];
}

export function moduleForPath(pathname, routeModuleMap = ROUTE_MODULE_MAP) {
  const pathKey = Object.keys(routeModuleMap)
    .sort((a, b) => b.length - a.length)
    .find((p) => pathname === p || pathname.startsWith(`${p}/`));
  return pathKey ? routeModuleMap[pathKey] : null;
}

export function navSectionGrantedByPermissions(sectionId, permissions, sectionModules = NAV_SECTION_MODULES) {
  const mapping = sectionModules[sectionId];
  if (!mapping) return false;
  if (!Array.isArray(permissions)) return false;
  const modules = Array.isArray(mapping) ? mapping : [mapping];
  return permissions.some((p) => modules.includes(p.module));
}
