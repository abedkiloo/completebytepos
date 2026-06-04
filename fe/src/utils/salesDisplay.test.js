import { installLocalStorageMock } from '../test-utils';
import {
  salesShowDiscount,
  salesShowTax,
  salesShowDelivery,
  salesRequireCustomer,
  salesAllowPartialPayment,
  salesAllowExcessToWallet,
  salesValidateStock,
} from './salesDisplay';

describe('salesDisplay', () => {
  beforeEach(() => {
    installLocalStorageMock();
    localStorage.setItem('profile', JSON.stringify({ role: 'manager' }));
  });

  test('checkout display flags default on for managers', () => {
    expect(salesShowDiscount({})).toBe(true);
    expect(salesShowTax({})).toBe(true);
    expect(salesShowDelivery({})).toBe(true);
    expect(salesValidateStock({})).toBe(true);
  });

  test('require_customer defaults off', () => {
    expect(salesRequireCustomer({})).toBe(false);
  });

  test('payment flags default on', () => {
    expect(salesAllowPartialPayment({})).toBe(true);
    expect(salesAllowExcessToWallet({})).toBe(true);
  });

  test('flags respect explicit false', () => {
    const off = {
      show_discount: false,
      show_tax: false,
      show_delivery: false,
      require_customer: true,
      allow_partial_payment: false,
      allow_excess_to_wallet: false,
      validate_stock_before_sale: false,
    };
    expect(salesShowDiscount(off)).toBe(false);
    expect(salesShowTax(off)).toBe(false);
    expect(salesShowDelivery(off)).toBe(false);
    expect(salesRequireCustomer(off)).toBe(true);
    expect(salesAllowPartialPayment(off)).toBe(false);
    expect(salesAllowExcessToWallet(off)).toBe(false);
    expect(salesValidateStock(off)).toBe(false);
  });
});
