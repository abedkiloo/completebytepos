import {
  PAYMENT_METHODS,
  filterEnabledPaymentMethods,
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
});
