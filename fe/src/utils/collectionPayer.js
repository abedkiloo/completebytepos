/**
 * Payer name / phone and M-Pesa till vs bank for debt collections.
 */

import { isModuleFeatureEnabled } from './moduleFeatures';

export const MPESA_DESTINATION_TILL = 'till';
export const MPESA_DESTINATION_BANK = 'bank';

export const MPESA_DESTINATION_OPTIONS = [
  { value: MPESA_DESTINATION_TILL, label: 'Till' },
  { value: MPESA_DESTINATION_BANK, label: 'Bank' },
];

export function collectionPayerDetailsEnabled() {
  return isModuleFeatureEnabled('customers', 'collection_payer_details', true);
}

export function mpesaDestinationLabel(value) {
  const key = String(value || '').trim().toLowerCase();
  const match = MPESA_DESTINATION_OPTIONS.find((o) => o.value === key);
  return match ? match.label : '';
}

/** Digits only (keeps leading +). */
export function normalizePayerPhone(raw) {
  const text = String(raw || '').trim();
  if (!text) return '';
  if (text.startsWith('+')) {
    return `+${text.slice(1).replace(/\D+/g, '')}`.slice(0, 32);
  }
  return text.replace(/\D+/g, '').slice(0, 32);
}

/**
 * Client-side validation mirroring sales.collection_payer.validate_collection_payer_fields.
 *
 * @returns {{ payer_name?: string, payer_phone?: string, mpesa_destination?: string }}
 */
export function validateCollectionPayerFields({
  paymentMethod,
  reference = '',
  payerName = '',
  payerPhone = '',
  mpesaDestination = '',
  requirePayer = true,
  requireMpesaDestinationForCode = true,
} = {}) {
  const errors = {};
  const name = String(payerName || '').trim().slice(0, 120);
  const phone = normalizePayerPhone(payerPhone);
  const method = String(paymentMethod || '').trim().toLowerCase();
  const ref = String(reference || '').trim();
  let dest = String(mpesaDestination || '').trim().toLowerCase();

  if (method !== 'mpesa') {
    dest = '';
  } else if (dest && dest !== MPESA_DESTINATION_TILL && dest !== MPESA_DESTINATION_BANK) {
    errors.mpesa_destination = 'Choose whether the M-Pesa code came via till or bank.';
    dest = '';
  }

  if (requirePayer) {
    if (!name) errors.payer_name = 'Enter the name of who paid.';
    if (!phone) {
      errors.payer_phone = 'Enter the phone number of who paid.';
    } else if (phone.replace(/\D+/g, '').length < 9) {
      errors.payer_phone = 'Enter a valid phone number (at least 9 digits).';
    }
  }

  if (requireMpesaDestinationForCode && method === 'mpesa' && ref && !dest) {
    errors.mpesa_destination =
      'Say whether this M-Pesa code came via till or bank before saving.';
  }

  return errors;
}
