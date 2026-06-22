/**
 * POS checkout pre-flight checks (pure helpers for tests + usePOSState).
 */

export function isRegisteredPosCustomer(customer) {
  return Boolean(customer?.id && customer.id !== 'walk-in');
}

/**
 * Validate "amount received" for cash/M-Pesa before completing or opening debt confirm.
 * When paymentOnAccount is on, empty amount means full pay later (0 received).
 */
export function evaluatePosAmountReceived(receivedAmount, options = {}) {
  const {
    allowPartialPayment = false,
    hasRegisteredCustomer = false,
    paymentOnAccount = false,
  } = options;

  const accountMode = paymentOnAccount && allowPartialPayment && hasRegisteredCustomer;

  if (receivedAmount === '' || receivedAmount === null || receivedAmount === undefined) {
    if (accountMode) {
      return { ok: true, received: 0, creditSale: true, fullPayLater: true };
    }
    return {
      ok: false,
      message: 'Enter the amount received from the customer.',
    };
  }

  const received = parseFloat(receivedAmount);
  if (!Number.isFinite(received) || received < 0) {
    return {
      ok: false,
      message: 'Enter a valid amount received.',
    };
  }

  if (received === 0) {
    if (allowPartialPayment && hasRegisteredCustomer) {
      return { ok: true, received: 0, creditSale: true, fullPayLater: true };
    }
    return {
      ok: false,
      message: 'Enter the amount received from the customer.',
    };
  }

  return { ok: true, received };
}

/** Billing POS: allow 0 or empty when payment-on-account mode is on. */
export function evaluateBillingAmountPaid(rawPaid, options = {}) {
  const {
    paymentMethod = 'cash',
    partialPayment = false,
    hasRegisteredCustomer = false,
    total = 0,
  } = options;

  if (paymentMethod === 'other') {
    return { ok: true, paid: total };
  }

  const accountMode = partialPayment && hasRegisteredCustomer;

  if (rawPaid === '' || rawPaid === null || rawPaid === undefined) {
    if (accountMode) {
      return { ok: true, paid: 0, creditSale: true, fullPayLater: true };
    }
    return { ok: false, message: 'Enter amount received' };
  }

  const paid = parseFloat(rawPaid);
  if (!Number.isFinite(paid) || paid < 0) {
    return { ok: false, message: 'Enter amount received' };
  }

  if (paid === 0) {
    if (accountMode) {
      return { ok: true, paid: 0, creditSale: true, fullPayLater: true };
    }
    return { ok: false, message: 'Enter amount received' };
  }

  return { ok: true, paid };
}
