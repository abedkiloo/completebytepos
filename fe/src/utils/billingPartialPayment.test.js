import {
  canEnablePartialPayment,
  evaluatePartialPaymentToggle,
} from './billingPartialPayment';
import { WALK_IN_CUSTOMER } from './walkInCustomer';

describe('billingPartialPayment', () => {
  const registered = { id: 12, name: 'Jane Doe', phone: '0700000000' };

  it('cannot enable partial payment for walk-in', () => {
    expect(canEnablePartialPayment(WALK_IN_CUSTOMER)).toBe(false);
    expect(canEnablePartialPayment(null)).toBe(false);
    expect(canEnablePartialPayment({ id: 'walk-in' })).toBe(false);
  });

  it('can enable partial payment for a registered customer', () => {
    expect(canEnablePartialPayment(registered)).toBe(true);
  });

  it('allows unchecking partial payment regardless of customer', () => {
    expect(evaluatePartialPaymentToggle(false, WALK_IN_CUSTOMER)).toEqual({ allow: true });
    expect(evaluatePartialPaymentToggle(false, registered)).toEqual({ allow: true });
  });

  it('blocks checking partial payment without a registered customer', () => {
    expect(evaluatePartialPaymentToggle(true, WALK_IN_CUSTOMER)).toEqual({
      allow: false,
      reason: 'customer_required',
    });
    expect(evaluatePartialPaymentToggle(true, null)).toEqual({
      allow: false,
      reason: 'customer_required',
    });
  });

  it('allows checking partial payment when customer is registered', () => {
    expect(evaluatePartialPaymentToggle(true, registered)).toEqual({ allow: true });
  });
});
