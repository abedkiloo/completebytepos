/**
 * Role + permission helpers for the three bootstrap personas.
 * Data comes from GET /api/accounts/auth/me/ (stored after login).
 */
import { normalizeModuleSettings, isRichModulePayload } from './moduleCache';
import { readCachedStoreSettings } from './storeSettingsCache';

export const PERSONA = {
  SUPER_ADMIN: 'super_admin',
  MANAGER: 'manager',
  SALES: 'sales',
};

/** All in-app routes (keep in sync with App.js). */
export const APP_ROUTE_PREFIXES = [
  '/',
  '/pos',
  '/products',
  '/categories',
  '/sales',
  '/inventory',
  '/barcodes',
  '/reports',
  '/expenses',
  '/accounting',
  '/income',
  '/users',
  '/roles',
  '/customers',
  '/suppliers',
  '/employees',
  '/normal-sale',
  '/module-settings',
  '/system-settings',
  '/invoices',
  '/branches',
];

const SUPER_ADMIN_ONLY_PREFIXES = new Set([
  '/users',
  '/roles',
  '/module-settings',
  '/system-settings',
  '/branches',
]);

/**
 * Route prefixes each persona may open.
 * `null` = unrestricted (super admin).
 */
export const ALLOWED_ROUTE_PREFIXES = {
  [PERSONA.SUPER_ADMIN]: null,
  [PERSONA.MANAGER]: APP_ROUTE_PREFIXES.filter((p) => !SUPER_ADMIN_ONLY_PREFIXES.has(p)),
  [PERSONA.SALES]: ['/', '/pos', '/customers'],
};

export function getStoredAuth() {
  try {
    const user = JSON.parse(localStorage.getItem('user') || 'null');
    const profile = JSON.parse(localStorage.getItem('profile') || 'null');
    const permissions = JSON.parse(localStorage.getItem('permissions') || '[]');
    const enabledModules = JSON.parse(localStorage.getItem('enabled_modules') || '{}');
    return { user, profile, permissions, enabledModules };
  } catch {
    return { user: null, profile: null, permissions: [], enabledModules: {} };
  }
}

export function resolvePersona(mePayload) {
  const profile = mePayload?.profile;
  const user = mePayload?.user;
  const role = profile?.role;
  const customName = profile?.custom_role?.name;
  if (
    mePayload?.is_super_admin ||
    user?.is_superuser ||
    role === 'super_admin' ||
    customName === 'Super Admin'
  ) {
    return PERSONA.SUPER_ADMIN;
  }
  if (role === 'manager' || customName === 'Manager') {
    return PERSONA.MANAGER;
  }
  return PERSONA.SALES;
}

export function getPersonaFromStorage() {
  const { user, profile } = getStoredAuth();
  return resolvePersona({
    user,
    profile,
    is_super_admin:
      user?.is_superuser ||
      profile?.role === 'super_admin' ||
      profile?.is_super_admin,
  });
}

/** Super admin or manager — not front-line sales/cashier. */
export function isManagerOrAdminFromStorage() {
  const persona = getPersonaFromStorage();
  return persona === PERSONA.SUPER_ADMIN || persona === PERSONA.MANAGER;
}

export function hasPermission(permissions, module, action) {
  if (!Array.isArray(permissions)) return false;
  const key = `${module}.${action}`;
  return permissions.some((p) => p.name === key || (p.module === module && p.action === action));
}

function pathMatchesPrefix(pathname, prefix) {
  if (prefix === '/') {
    return pathname === '/';
  }
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

/** Nav path → module that must be enabled (manager/sales). Super admin ignores. */
export const ROUTE_MODULE_MAP = {
  '/products': 'products',
  '/categories': 'products',
  '/barcodes': 'barcodes',
  '/inventory': 'stock',
  '/suppliers': 'suppliers',
  '/employees': 'employees',
  '/pos': 'sales',
  '/pos/billing': 'sales',
  '/normal-sale': 'sales',
  '/sales': 'sales',
  '/customers': 'customers',
  '/invoices': 'invoicing',
  '/reports': 'reports',
  '/accounting': 'accounting',
  '/expenses': 'expenses',
  '/income': 'income',
  '/users': 'settings',
  '/roles': 'settings',
  '/module-settings': 'settings',
  '/branches': 'settings',
  '/system-settings': 'settings',
};

function salesRoutePrefixes() {
  const base = ALLOWED_ROUTE_PREFIXES[PERSONA.SALES];
  const store = readCachedStoreSettings();
  if (store.allow_sales_add_products) {
    return [...base, '/products', '/categories'];
  }
  return base;
}

export function canAccessRoute(persona, pathname, options = {}) {
  const { isSuperAdmin = false, moduleSettings = null, loadingModules = false } = options;

  if (isSuperAdmin || persona === PERSONA.SUPER_ADMIN) {
    return true;
  }

  const allowed =
    persona === PERSONA.SALES
      ? salesRoutePrefixes()
      : ALLOWED_ROUTE_PREFIXES[persona];
  const list = allowed === null ? APP_ROUTE_PREFIXES : allowed || ALLOWED_ROUTE_PREFIXES[PERSONA.SALES];
  const routeAllowed = list.some((prefix) => pathMatchesPrefix(pathname, prefix));
  if (!routeAllowed) return false;

  const pathKey = Object.keys(ROUTE_MODULE_MAP).find(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );
  if (!pathKey || !moduleSettings || loadingModules) {
    return true;
  }

  const moduleName = ROUTE_MODULE_MAP[pathKey];
  const mod = moduleSettings[moduleName];
  if (mod == null) return true;
  if (typeof mod === 'boolean') return mod;
  return Boolean(mod.is_enabled);
}

export function persistMeResponse(data) {
  if (data?.user) {
    localStorage.setItem('user', JSON.stringify(data.user));
  }
  if (data?.profile) {
    localStorage.setItem('profile', JSON.stringify(data.profile));
  }
  if (data?.permissions) {
    localStorage.setItem('permissions', JSON.stringify(data.permissions));
  }
  if (data?.enabled_modules && isRichModulePayload(data.enabled_modules)) {
    localStorage.setItem(
      'enabled_modules',
      JSON.stringify(normalizeModuleSettings(data.enabled_modules))
    );
  }
}
