import { isModuleFlagEnabled } from './moduleSettingsCache';

export function suppliersShowSupplierCode(settings) {
  return isModuleFlagEnabled(settings, 'show_supplier_code', true);
}

export function suppliersShowSupplierType(settings) {
  return isModuleFlagEnabled(settings, 'show_supplier_type', true);
}

export function suppliersShowContactDetails(settings) {
  return isModuleFlagEnabled(settings, 'show_contact_details', true);
}

export function suppliersShowBusinessDetails(settings) {
  return isModuleFlagEnabled(settings, 'show_business_details', true);
}

export function suppliersShowPaymentTerms(settings) {
  return isModuleFlagEnabled(settings, 'show_payment_terms', true);
}

export function suppliersShowCreditFields(settings) {
  return isModuleFlagEnabled(settings, 'show_credit_fields', true);
}

export function suppliersShowRating(settings) {
  return isModuleFlagEnabled(settings, 'show_supplier_rating', true);
}

export function suppliersShowPreferredFlag(settings) {
  return isModuleFlagEnabled(settings, 'show_preferred_flag', true);
}

export function suppliersShowNotes(settings) {
  return isModuleFlagEnabled(settings, 'show_supplier_notes', true);
}

export function suppliersShowStatus(supplierModuleSettings, storeSettings) {
  if (storeSettings?.hide_entity_status_toggles) return false;
  return isModuleFlagEnabled(supplierModuleSettings, 'show_supplier_status', true);
}

export function suppliersEnableCreate(settings) {
  return isModuleFlagEnabled(settings, 'enable_supplier_create', true);
}

export function suppliersEnableEdit(settings) {
  return isModuleFlagEnabled(settings, 'enable_supplier_edit', true);
}

export function suppliersEnableDelete(settings) {
  return isModuleFlagEnabled(settings, 'enable_supplier_delete', true);
}

export function suppliersEnableStatistics(settings) {
  return isModuleFlagEnabled(settings, 'enable_supplier_statistics', true);
}

export function suppliersEnableProducts(settings) {
  return isModuleFlagEnabled(settings, 'enable_supplier_products', true);
}
