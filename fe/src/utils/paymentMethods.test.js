import {
  COLLECTION_PAYMENT_METHODS,
  PAYMENT_METHODS,
  filterEnabledPaymentMethods,
  getPaymentMethodMeta,
  paymentReferencePlaceholder,
  paymentReferenceRequired,
  paymentReferenceLabel,
  paymentMethodLabel,
} from './paymentMethods';

describe('paymentMethods', () => {
  test('collection methods are cash and mpesa only', () => {
    expect(COLLECTION_PAYMENT_METHODS.map((m) => m.id)).toEqual(['cash', 'mpesa']);
  });

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
    const result = filterEnabledPaymentMethods(['CASH', 'Mpesa']);
    expect(result.map((m) => m.id)).toEqual(['cash', 'mpesa']);
  });

  test('paymentReferenceRequired for non-cash methods', () => {
    expect(paymentReferenceRequired('cash')).toBe(false);
    expect(paymentReferenceRequired('wallet')).toBe(false);
    expect(paymentReferenceRequired('mpesa')).toBe(true);
  });

  test('paymentReferenceLabel for mpesa', () => {
    expect(paymentReferenceLabel('mpesa')).toBe('M-Pesa code');
  });

  test('getPaymentMethodMeta falls back to cash', () => {
    expect(getPaymentMethodMeta('unknown').id).toBe('cash');
    expect(getPaymentMethodMeta('mpesa').referenceLabel).toBe('M-Pesa code');
  });

  test('paymentReferencePlaceholder', () => {
    expect(paymentReferencePlaceholder('mpesa')).toContain('QHX');
    expect(paymentReferencePlaceholder('cash')).toBe('Enter reference');
  });

  test('paymentMethodLabel keeps historical methods', () => {
    expect(paymentMethodLabel('installments')).toBe('Installments');
    expect(paymentMethodLabel('other')).toBe('Other');
    expect(paymentMethodLabel('card')).toBe('Card');
    expect(paymentMethodLabel('bank_transfer')).toBe('Bank Transfer');
    expect(paymentMethodLabel('cheque')).toBe('Cheque');
    expect(paymentMethodLabel('cash')).toBe('Cash');
  });
});
