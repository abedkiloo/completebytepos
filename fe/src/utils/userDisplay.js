import { isModuleFlagEnabled } from './moduleSettingsCache';

export function usersShowEmail(settings) {
  return isModuleFlagEnabled(settings, 'show_user_email', true);
}

export function usersShowPhone(settings) {
  return isModuleFlagEnabled(settings, 'show_user_phone', true);
}

export function usersShowFullName(settings) {
  return isModuleFlagEnabled(settings, 'show_user_full_name', true);
}

export function usersShowStatus(userModuleSettings, storeSettings) {
  if (storeSettings?.hide_entity_status_toggles) return false;
  return isModuleFlagEnabled(userModuleSettings, 'show_user_status', true);
}

export function usersShowDateJoined(settings) {
  return isModuleFlagEnabled(settings, 'show_date_joined', true);
}

export function usersShowStatistics(settings) {
  return isModuleFlagEnabled(settings, 'show_user_statistics', true);
}

export function usersShowStaffFlag(settings) {
  return isModuleFlagEnabled(settings, 'show_staff_flag', true);
}

export function usersEnableCreate(settings) {
  return isModuleFlagEnabled(settings, 'enable_user_create', true);
}

export function usersEnableEdit(settings) {
  return isModuleFlagEnabled(settings, 'enable_user_edit', true);
}

export function usersEnableDelete(settings) {
  return isModuleFlagEnabled(settings, 'enable_user_delete', true);
}

export function usersEnableInlineRoleAssignment(settings) {
  return isModuleFlagEnabled(settings, 'enable_inline_role_assignment', true);
}

export function usersEnableRoleCreate(settings) {
  return isModuleFlagEnabled(settings, 'enable_role_create', true);
}

export function usersEnableRoleEdit(settings) {
  return isModuleFlagEnabled(settings, 'enable_role_edit', true);
}

export function usersEnableRoleDelete(settings) {
  return isModuleFlagEnabled(settings, 'enable_role_delete', true);
}

export function usersEnablePermissionCatalog(settings) {
  return isModuleFlagEnabled(settings, 'enable_permission_catalog', true);
}
