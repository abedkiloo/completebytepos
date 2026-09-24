import { AMOUNT_EXAMPLE, moneyMessage, parseMoney } from './formValidation';

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
      message: `Enter the amount received, e.g. ${AMOUNT_EXAMPLE}`,
    };
  }

  const formatErr = moneyMessage(receivedAmount, { allowZero: true });
  if (formatErr) {
    return { ok: false, message: formatErr };
  }
  const received = parseMoney(receivedAmount, { allowZero: true });

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
    partialPayment = false,
    hasRegisteredCustomer = false,
  } = options;

  const accountMode = partialPayment && hasRegisteredCustomer;

  if (rawPaid === '' || rawPaid === null || rawPaid === undefined) {
    if (accountMode) {
      return { ok: true, paid: 0, creditSale: true, fullPayLater: true };
    }
    return { ok: false, message: `Enter the amount received, e.g. ${AMOUNT_EXAMPLE}` };
  }

  const formatErr = moneyMessage(rawPaid, { allowZero: true });
  if (formatErr) {
    return { ok: false, message: formatErr };
  }
  const paid = parseMoney(rawPaid, { allowZero: true });

  if (paid === 0) {
    if (accountMode) {
      return { ok: true, paid: 0, creditSale: true, fullPayLater: true };
    }
    return { ok: false, message: 'Enter amount received' };
  }

  return { ok: true, paid };
}
