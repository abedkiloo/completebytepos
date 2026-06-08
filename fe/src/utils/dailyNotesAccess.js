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

export function userMayViewAllDailyNotes(persona, moduleSettings = {}) {
  const { permissions } = getStoredAuth();
  if (!hasPermission(permissions, 'daily_notes', 'view_all')) {
    return false;
  }
  if (persona === PERSONA.SUPER_ADMIN) {
    return true;
  }
  if (persona === PERSONA.MANAGER) {
    return managerViewAllDailyNotes(moduleSettings);
  }
  if (persona === PERSONA.SALES) {
    return salesViewAllDailyNotes(moduleSettings);
  }
  return false;
}
