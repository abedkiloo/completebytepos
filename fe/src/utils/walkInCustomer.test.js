import {
  WALK_IN_CUSTOMER,
  isWalkInCustomer,
  mergeCustomersWithWalkIn,
  prependCustomerToList,
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

  it('prependCustomerToList selects new customer in picker order', () => {
    const list = prependCustomerToList(
      mergeCustomersWithWalkIn([{ id: 1, name: 'A' }]),
      { id: 2, name: 'B' }
    );
    expect(list[0].id).toBe('walk-in');
    expect(list[1]).toEqual({ id: 2, name: 'B' });
    expect(list).toHaveLength(3);
  });

  it('customerIdForSale returns null for walk-in', () => {
    expect(customerIdForSale(WALK_IN_CUSTOMER)).toBeNull();
    expect(customerIdForSale({ id: 5 })).toBe(5);
  });
});
