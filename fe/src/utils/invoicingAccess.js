import { isModuleFeatureEnabled } from './moduleFeatures';
import { isModuleEnabled } from './moduleSettings';

function invoicingModuleActive() {
  return isModuleEnabled('invoicing');
}

export function invoiceCreationAllowed() {
  return (
    invoicingModuleActive() &&
    isModuleFeatureEnabled('invoicing', 'invoice_creation', false)
  );
}

export function invoiceTrackingAllowed() {
  return (
    invoicingModuleActive() &&
    isModuleFeatureEnabled('invoicing', 'invoice_tracking', false)
  );
}

export function paymentTrackingAllowed() {
  return (
    invoicingModuleActive() &&
    isModuleFeatureEnabled('invoicing', 'payment_tracking', false)
  );
}
