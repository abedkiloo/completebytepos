import {
  ACCOUNT_PAYMENT_LABEL,
  computeAccountBalanceDue,
  isFullPayLater,
} from './accountPayment';

describe('accountPayment', () => {
  test('computeAccountBalanceDue returns remaining balance', () => {
    expect(computeAccountBalanceDue(100, 40)).toBe(60);
    expect(computeAccountBalanceDue(100, 100)).toBe(0);
    expect(computeAccountBalanceDue(100, 150)).toBe(0);
  });

  test('isFullPayLater is true only for zero paid with positive total', () => {
    expect(isFullPayLater(500, 0)).toBe(true);
    expect(isFullPayLater(500, 100)).toBe(false);
    expect(isFullPayLater(0, 0)).toBe(false);
  });

  test('ACCOUNT_PAYMENT_LABEL is stable for UI', () => {
    expect(ACCOUNT_PAYMENT_LABEL).toMatch(/customer account/i);
  });
});
