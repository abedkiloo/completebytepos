import {
  evaluateBillingAmountPaid,
  evaluatePosAmountReceived,
  isRegisteredPosCustomer,
} from './posCheckoutValidation';

describe('posCheckoutValidation', () => {
  test('isRegisteredPosCustomer excludes walk-in', () => {
    expect(isRegisteredPosCustomer({ id: 'walk-in', name: 'Walk-in' })).toBe(false);
    expect(isRegisteredPosCustomer({ id: 5, name: 'Alice' })).toBe(true);
  });

  test('evaluatePosAmountReceived rejects empty and non-numeric', () => {
    expect(evaluatePosAmountReceived('', {}).ok).toBe(false);
    expect(evaluatePosAmountReceived('abc', {}).ok).toBe(false);
  });

  test('evaluatePosAmountReceived rejects zero without partial + customer', () => {
    expect(evaluatePosAmountReceived('0', { allowPartialPayment: false }).ok).toBe(false);
    expect(
      evaluatePosAmountReceived('0', {
        allowPartialPayment: true,
        hasRegisteredCustomer: false,
      }).ok
    ).toBe(false);
  });

  test('evaluatePosAmountReceived allows zero for credit sale', () => {
    expect(
      evaluatePosAmountReceived('0', {
        allowPartialPayment: true,
        hasRegisteredCustomer: true,
      })
    ).toEqual({ ok: true, received: 0, creditSale: true, fullPayLater: true });
  });

  test('evaluateBillingAmountPaid allows empty when payment on account', () => {
    expect(
      evaluateBillingAmountPaid('', {
        partialPayment: true,
        hasRegisteredCustomer: true,
      })
    ).toEqual({ ok: true, paid: 0, creditSale: true, fullPayLater: true });
  });

  test('evaluateBillingAmountPaid allows partial amount on account', () => {
    expect(
      evaluateBillingAmountPaid('150', {
        partialPayment: true,
        hasRegisteredCustomer: true,
        total: 500,
      })
    ).toEqual({ ok: true, paid: 150 });
  });

  test('evaluateBillingAmountPaid rejects empty without payment on account', () => {
    expect(
      evaluateBillingAmountPaid('', {
        partialPayment: false,
        hasRegisteredCustomer: true,
      }).ok
    ).toBe(false);
  });

  test('evaluatePosAmountReceived empty is credit when payment on account', () => {
    expect(
      evaluatePosAmountReceived('', {
        allowPartialPayment: true,
        hasRegisteredCustomer: true,
        paymentOnAccount: true,
      })
    ).toEqual({ ok: true, received: 0, creditSale: true, fullPayLater: true });
  });

  test('evaluatePosAmountReceived accepts a tendered amount', () => {
    expect(evaluatePosAmountReceived('250.00', {})).toEqual({
      ok: true,
      received: 250,
    });
  });

  test('evaluateBillingAmountPaid rejects invalid and zero without account', () => {
    expect(evaluateBillingAmountPaid('abc', {}).ok).toBe(false);
    expect(evaluateBillingAmountPaid('0', { partialPayment: false }).ok).toBe(false);
    expect(
      evaluateBillingAmountPaid('0', {
        partialPayment: true,
        hasRegisteredCustomer: true,
      })
    ).toEqual({ ok: true, paid: 0, creditSale: true, fullPayLater: true });
  });
});
