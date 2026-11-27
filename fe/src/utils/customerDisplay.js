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

export function customersEnableWalletPayment(settings) {
  return isModuleFlagEnabled(settings, 'enable_wallet_payment', true);
}

export function customersEnableCreate(settings) {
  return isModuleFlagEnabled(settings, 'enable_customer_create', true);
}

export function customersEnableEdit(settings) {
  return isModuleFlagEnabled(settings, 'enable_customer_edit', true);
}

/**
 * Web + app: edit when the store allows it and the user can create or update customers.
 * Matches mobile `canEditCustomers` and BE update (create OR update).
 */
export function canEditCustomer(settings, permissions = [], { isManagerOrAdmin = false } = {}) {
  if (!customersEnableEdit(settings)) return false;
  if (isManagerOrAdmin) return true;
  if (!Array.isArray(permissions)) return false;
  return permissions.some(
    (p) =>
      p.name === 'customers.update' ||
      p.name === 'customers.create' ||
      (p.module === 'customers' && (p.action === 'update' || p.action === 'create'))
  );
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

/**
 * Quick-add at POS: module flag plus create permission (manager/admin OR customers.create).
 */
export function canQuickAddCustomerAtPos(
  roleAllowed,
  customerModuleSettings,
  permissions = []
) {
  if (!customersAllowQuickAddAtPos(customerModuleSettings)) {
    return false;
  }
  if (roleAllowed) {
    return true;
  }
  if (!Array.isArray(permissions)) {
    return false;
  }
  return permissions.some(
    (p) =>
      p.name === 'customers.create' ||
      (p.module === 'customers' && p.action === 'create')
  );
}

/**
 * True when the customer row has a snapped map pin (lat −90..90, lng −180..180).
 *
 * @param {object|null|undefined} customer
 * @returns {boolean}
 */
export function customerHasLocationPing(customer) {
  if (!customer) return false;
  const lat = Number(customer.latitude);
  const lng = Number(customer.longitude);
  return Number.isFinite(lat) && Number.isFinite(lng);
}

/**
 * Human-readable GPS coordinates for detail cards.
 *
 * @param {object|null|undefined} customer
 * @returns {string} Empty when no ping; otherwise `"lat, lng"` with 5 decimals.
 */
export function formatCustomerLocationPing(customer) {
  if (!customerHasLocationPing(customer)) return '';
  const lat = Number(customer.latitude).toFixed(5);
  const lng = Number(customer.longitude).toFixed(5);
  return `${lat}, ${lng}`;
}

/**
 * Open-maps URL for a snapped pin (max ~80 chars).
 *
 * @param {object|null|undefined} customer
 * @returns {string|null}
 */
export function customerMapsUrl(customer) {
  if (!customerHasLocationPing(customer)) return null;
  const lat = Number(customer.latitude);
  const lng = Number(customer.longitude);
  return `https://maps.google.com/?q=${lat},${lng}`;
}

/**
 * Place line from address + Kenya admin units (no GPS).
 *
 * @param {object|null|undefined} customer
 * @returns {string}
 */
export function formatCustomerPlaceLine(customer) {
  if (!customer) return '';
  const admin = [customer.ward, customer.sub_county, customer.county || customer.city]
    .filter(Boolean)
    .join(', ');
  return [customer.address, admin, customer.country].filter(Boolean).join(' · ');
}
