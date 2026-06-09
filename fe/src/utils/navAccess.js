/**
 * Sidebar visibility by persona + permissions.
 * Works with Layout NAV_SECTIONS and module feature flags.
 */
import {
  PERSONA,
  resolvePersona,
  hasPermission,
  hasAnyPermissionForModule,
  getStoredAuth,
} from './roleAccess';
import { localRegistryFeatureDefault } from '../config/moduleFeatureDefaults';
import {
  normalizeModuleSettings,
  isModuleEnabledInSettings,
  isFeatureEnabledInSettings,
  registryFeatureDefault,
} from './moduleCache';
import { readCachedModuleSettings } from './moduleSettingsCache';
import { readCachedStoreSettings } from './storeSettingsCache';
import { salesCatalogAccessEnabled } from './productAccess';

/** Section ids visible per persona (`null` = all sections). */
export const VISIBLE_SECTIONS = {
  [PERSONA.SUPER_ADMIN]: null,
  [PERSONA.MANAGER]: [
    'main',
    'inventory',
    'stock',
    'suppliers',
    'employees',
    'sales',
    'customers',
    'invoicing',
    'reports',
    'accounting',
  ],
  [PERSONA.SALES]: ['main', 'sales', 'customers'],
};

/** Sales nav: cashiers only need fast checkout paths. */
const SALES_ONLY_PATHS = new Set(['/pos', '/pos/billing']);

/** Nav sections unlocked for sales when their role includes module permissions. */
const SECTION_PERMISSION_MODULE = {
  invoicing: 'invoicing',
  reports: 'reports',
  accounting: ['accounting', 'expenses', 'income'],
  stock: 'stock',
  suppliers: 'suppliers',
  employees: 'employees',
};

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

export function isSuperAdminFromStorage() {
  const { user, profile } = getStoredAuth();
  return (
    user?.is_superuser ||
    profile?.role === 'super_admin' ||
    profile?.is_super_admin ||
    profile?.custom_role?.name === 'Super Admin'
  );
}

function sectionAllowedForPersona(sectionId, persona, permissions = []) {
  if (persona === PERSONA.SALES && sectionId === 'inventory') {
    return salesCatalogAccessEnabled(
      readCachedModuleSettings('products'),
      readCachedStoreSettings()
    );
  }
  if (persona === PERSONA.SALES && sectionId === 'sales') {
    return true;
  }
  const allowed = VISIBLE_SECTIONS[persona];
  if (allowed === null) return true;
  if (allowed.includes(sectionId)) return true;
  if (persona === PERSONA.SALES && SECTION_PERMISSION_MODULE[sectionId]) {
    return hasAnyPermissionForModule(permissions, SECTION_PERMISSION_MODULE[sectionId]);
  }
  return false;
}

/**
 * Whether a nav leaf link should render for the current user.
 */
export function canSeeNavItem(item, sectionId, ctx) {
  const {
    persona,
    isSuperAdmin,
    permissions,
    isModuleEnabled,
    isFeatureEnabled,
  } = ctx;

  if (!sectionAllowedForPersona(sectionId, persona, permissions)) return false;

  if (item.requireSuperAdmin && !isSuperAdmin) return false;
  if (item.managerOnly && persona === PERSONA.SALES) return false;

  if (persona === PERSONA.SALES) {
    const path = item.to.split('?')[0];
    const salesCatalog = salesCatalogAccessEnabled(
      readCachedModuleSettings('products'),
      readCachedStoreSettings()
    );
    if (item.salesCatalogItem) {
      return salesCatalog;
    }
    if (path === '/products' || path === '/categories') {
      return salesCatalog;
    }
    if (sectionId === 'inventory') return false;
    if (sectionId === 'sales' && !SALES_ONLY_PATHS.has(path)) return false;
    if (sectionId === 'settings') return false;
    if (sectionId === 'reports' || sectionId === 'accounting') return false;
    if (sectionId === 'inventory' || sectionId === 'stock' || sectionId === 'suppliers') {
      return false;
    }
  }

  if (persona === PERSONA.MANAGER) {
    if (item.requireSuperAdmin) return false;
    if (item.to === '/module-settings' || item.to === '/branches') return false;
    if (sectionId === 'settings' && item.to === '/roles') {
      return hasPermission(permissions, 'settings', 'role_management');
    }
  }

  if (item.module && !isModuleEnabled(item.module)) return false;
  if (item.feature && !isFeatureEnabled(item.feature[0], item.feature[1])) {
    return false;
  }

  if (item.permission) {
    const [mod, action] = item.permission;
    if (!hasPermission(permissions, mod, action)) return false;
  }

  return true;
}

export function buildNavContext(moduleSettings, loadingModules) {
  const { permissions } = getStoredAuth();
  const persona = getPersonaFromStorage();
  const isSuperAdmin = isSuperAdminFromStorage();
  const modules = normalizeModuleSettings(moduleSettings);

  const isModuleEnabled = (moduleName) =>
    isModuleEnabledInSettings(modules, moduleName, { loading: loadingModules });

  const isFeatureEnabled = (moduleName, featureKey) => {
    const defaultWhenMissing = modules?.registry?.feature_defaults
      ? registryFeatureDefault(modules, moduleName, featureKey)
      : localRegistryFeatureDefault(moduleName, featureKey);
    return isFeatureEnabledInSettings(modules, moduleName, featureKey, {
      loading: loadingModules,
      defaultWhenMissing,
    });
  };

  return {
    persona,
    isSuperAdmin,
    permissions,
    isModuleEnabled,
    isFeatureEnabled,
  };
}
