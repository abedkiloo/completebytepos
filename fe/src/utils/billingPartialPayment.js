import { isWalkInCustomer } from './walkInCustomer';

/** Partial payment posts balance to a registered customer account — not walk-in. */
export function canEnablePartialPayment(customer) {
  return !isWalkInCustomer(customer);
}

/**
 * @param {boolean} checked - desired checkbox state
 * @param {object|null|undefined} customer - selected customer
 * @returns {{ allow: boolean, reason?: string }}
 */
export function evaluatePartialPaymentToggle(checked, customer) {
  if (!checked) {
    return { allow: true };
  }
  if (canEnablePartialPayment(customer)) {
    return { allow: true };
  }
  return { allow: false, reason: 'customer_required' };
}
