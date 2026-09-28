/**
 * Daily notes access (mirrors be/daily_notes/access.py + module settings).
 */
import { PERSONA, hasPermission, getStoredAuth } from './roleAccess';
import { isModuleFlagEnabled } from './moduleSettingsCache';

export function salesDailyNotesAccessEnabled(settings = {}) {
  return isModuleFlagEnabled(settings, 'allow_sales_access', true);
}

export function managerViewAllDailyNotes(settings = {}) {
  return isModuleFlagEnabled(settings, 'allow_manager_view_all', true);
}

export function salesViewAllDailyNotes(settings = {}) {
  return isModuleFlagEnabled(settings, 'allow_sales_view_all', false);
}

/** Sales desk (POS / sales history) also unlocks Daily notes — returned-sale tasks. */
export function hasSalesDeskAccess(permissions) {
  return (
    hasPermission(permissions, 'daily_notes', 'view') ||
    hasPermission(permissions, 'sales', 'view') ||
    hasPermission(permissions, 'pos', 'view')
  );
}

export function userMayOpenDailyNotes(persona, permissions = [], moduleSettings = {}) {
  const { user, profile } = getStoredAuth();
  if (
    persona === PERSONA.SUPER_ADMIN ||
    user?.is_superuser ||
    profile?.is_super_admin
  ) {
    return true;
  }
  if (!hasSalesDeskAccess(permissions)) {
    return false;
  }
  if (persona === PERSONA.SALES && !salesDailyNotesAccessEnabled(moduleSettings)) {
    return false;
  }
  return true;
}

export function userMayViewAllDailyNotes(persona, moduleSettings = {}) {
  const { permissions, profile, user } = getStoredAuth();
  if (
    persona === PERSONA.SUPER_ADMIN ||
    user?.is_superuser ||
    profile?.is_super_admin ||
    profile?.role === 'super_admin' ||
    profile?.role === 'admin'
  ) {
    return true;
  }
  if (!hasPermission(permissions, 'daily_notes', 'view_all')) {
    return false;
  }
  if (persona === PERSONA.MANAGER) {
    return managerViewAllDailyNotes(moduleSettings);
  }
  if (persona === PERSONA.SALES) {
    return salesViewAllDailyNotes(moduleSettings);
  }
  return false;
}
