import { isModuleFlagEnabled } from './moduleSettingsCache';

export function employeesShowEmployeeId(settings) {
  return isModuleFlagEnabled(settings, 'show_employee_id', true);
}

export function employeesShowSalary(settings) {
  return isModuleFlagEnabled(settings, 'show_salary', false);
}

export function employeesShowDepartment(settings) {
  return isModuleFlagEnabled(settings, 'show_department', true);
}

export function employeesShowContactDetails(settings) {
  return isModuleFlagEnabled(settings, 'show_contact_details', true);
}

export function employeesShowNotes(settings) {
  return isModuleFlagEnabled(settings, 'show_employee_notes', true);
}

export function employeesShowStatus(employeeModuleSettings, storeSettings) {
  if (storeSettings?.hide_entity_status_toggles) return false;
  return isModuleFlagEnabled(employeeModuleSettings, 'show_employee_status', true);
}

export function employeesEnableCreate(settings) {
  return isModuleFlagEnabled(settings, 'enable_employee_create', true);
}

export function employeesEnableEdit(settings) {
  return isModuleFlagEnabled(settings, 'enable_employee_edit', true);
}

export function employeesEnableDelete(settings) {
  return isModuleFlagEnabled(settings, 'enable_employee_delete', true);
}

export function employeesEnableStatistics(settings) {
  return isModuleFlagEnabled(settings, 'enable_employee_statistics', true);
}
