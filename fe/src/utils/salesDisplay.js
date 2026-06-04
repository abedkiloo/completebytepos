import { isModuleFlagEnabled } from './moduleSettingsCache';
import { userMayEditFinancialFieldsFromStorage } from './roleAccess';

export function salesShowDiscount(settings) {
  if (!userMayEditFinancialFieldsFromStorage()) return false;
  return isModuleFlagEnabled(settings, 'show_discount', true);
}

export function salesShowTax(settings) {
  if (!userMayEditFinancialFieldsFromStorage()) return false;
  return isModuleFlagEnabled(settings, 'show_tax', true);
}

export function salesShowDelivery(settings) {
  return isModuleFlagEnabled(settings, 'show_delivery', true);
}

export function salesRequireCustomer(settings) {
  return isModuleFlagEnabled(settings, 'require_customer', false);
}

export function salesAllowPartialPayment(settings) {
  return isModuleFlagEnabled(settings, 'allow_partial_payment', true);
}

export function salesAllowExcessToWallet(settings) {
  return isModuleFlagEnabled(settings, 'allow_excess_to_wallet', true);
}

export function salesValidateStock(settings) {
  return isModuleFlagEnabled(settings, 'validate_stock_before_sale', true);
}
