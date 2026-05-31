import { isModuleFlagEnabled } from './moduleSettingsCache';

export function customersShowCustomerCode(settings) {
  return isModuleFlagEnabled(settings, 'show_customer_code', true);
}

export function customersShowOutstandingBalance(settings) {
  return isModuleFlagEnabled(settings, 'show_outstanding_balance', true);
}

export function customersShowWalletBalance(settings) {
  return isModuleFlagEnabled(settings, 'show_wallet_balance', true);
}

export function customersEnableCreate(settings) {
  return isModuleFlagEnabled(settings, 'enable_customer_create', true);
}

export function customersEnableEdit(settings) {
  return isModuleFlagEnabled(settings, 'enable_customer_edit', true);
}

export function customersEnableDelete(settings) {
  return isModuleFlagEnabled(settings, 'enable_customer_delete', true);
}

export function customersShowCustomerType(settings) {
  return isModuleFlagEnabled(settings, 'show_customer_type', true);
}

export function customersShowTaxId(settings) {
  return isModuleFlagEnabled(settings, 'show_tax_id', true);
}

export function customersShowNotes(settings) {
  return isModuleFlagEnabled(settings, 'show_customer_notes', true);
}

export function customersShowStatus(customerModuleSettings, storeSettings) {
  if (storeSettings?.hide_entity_status_toggles) return false;
  return isModuleFlagEnabled(customerModuleSettings, 'show_customer_status', true);
}

export function customersAllowQuickAddAtPos(settings) {
  return (
    isModuleFlagEnabled(settings, 'allow_quick_add_at_pos', true) &&
    customersEnableCreate(settings)
  );
}

/** Role check (manager/admin) plus module quick-add flag. */
export function canQuickAddCustomerAtPos(roleAllowed, customerModuleSettings) {
  return Boolean(roleAllowed) && customersAllowQuickAddAtPos(customerModuleSettings);
}
