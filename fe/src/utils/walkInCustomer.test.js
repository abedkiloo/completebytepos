import {
  WALK_IN_CUSTOMER,
  isWalkInCustomer,
  mergeCustomersWithWalkIn,
  customerIdForSale,
} from './walkInCustomer';

describe('walkInCustomer', () => {
  it('detects walk-in sentinel', () => {
    expect(isWalkInCustomer(null)).toBe(true);
    expect(isWalkInCustomer(WALK_IN_CUSTOMER)).toBe(true);
    expect(isWalkInCustomer({ id: 'walk-in' })).toBe(true);
    expect(isWalkInCustomer({ id: 42 })).toBe(false);
  });

  it('mergeCustomersWithWalkIn prepends walk-in once', () => {
    const list = mergeCustomersWithWalkIn([{ id: 1, name: 'A' }]);
    expect(list[0].id).toBe('walk-in');
    expect(list).toHaveLength(2);
  });

  it('customerIdForSale returns null for walk-in', () => {
    expect(customerIdForSale(WALK_IN_CUSTOMER)).toBeNull();
    expect(customerIdForSale({ id: 5 })).toBe(5);
  });
});
