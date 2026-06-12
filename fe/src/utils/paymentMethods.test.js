import {
  PAYMENT_METHODS,
  filterEnabledPaymentMethods,
  getPaymentMethodMeta,
  paymentReferencePlaceholder,
  paymentReferenceRequired,
  paymentReferenceLabel,
} from './paymentMethods';

describe('paymentMethods', () => {
  test('filterEnabledPaymentMethods returns all when unset', () => {
    const result = filterEnabledPaymentMethods(undefined);
    expect(result.map((m) => m.id)).toEqual(PAYMENT_METHODS.map((m) => m.id));
  });

  test('filterEnabledPaymentMethods respects enabled subset', () => {
    const result = filterEnabledPaymentMethods(['cash', 'mpesa']);
    expect(result.map((m) => m.id)).toEqual(['cash', 'mpesa']);
  });

  test('filterEnabledPaymentMethods falls back when empty after filter', () => {
    const result = filterEnabledPaymentMethods(['invalid']);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('cash');
  });

  test('filterEnabledPaymentMethods is case insensitive', () => {
    const result = filterEnabledPaymentMethods(['CASH', 'Card']);
    expect(result.map((m) => m.id)).toEqual(['cash', 'card']);
  });

  test('paymentReferenceRequired for non-cash methods', () => {
    expect(paymentReferenceRequired('cash')).toBe(false);
    expect(paymentReferenceRequired('wallet')).toBe(false);
    expect(paymentReferenceRequired('mpesa')).toBe(true);
    expect(paymentReferenceRequired('card')).toBe(true);
  });

  test('paymentReferenceLabel for mpesa', () => {
    expect(paymentReferenceLabel('mpesa')).toBe('M-Pesa code');
  });

  test('getPaymentMethodMeta falls back to cash', () => {
    expect(getPaymentMethodMeta('unknown').id).toBe('cash');
    expect(getPaymentMethodMeta('card').referenceLabel).toBe('Card reference');
  });

  test('paymentReferencePlaceholder', () => {
    expect(paymentReferencePlaceholder('mpesa')).toContain('QHX');
    expect(paymentReferencePlaceholder('cash')).toBe('Enter reference');
  });
});
