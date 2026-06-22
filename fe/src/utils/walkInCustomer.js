/** Virtual walk-in customer — not stored in DB; sale.customer_id stays null. */
export const WALK_IN_CUSTOMER = {
  id: 'walk-in',
  name: 'Walk-in customer',
  customer_code: 'WALK-IN',
  is_active: true,
};

export function isWalkInCustomer(customer) {
  if (!customer) return true;
  return customer.id === 'walk-in' || customer.id === WALK_IN_CUSTOMER.id;
}

/** Prepend a newly created customer to the picker list (deduped, walk-in preserved). */
export function prependCustomerToList(customers = [], newCustomer, { requireCustomer = false } = {}) {
  if (!newCustomer?.id) return Array.isArray(customers) ? customers : [];
  const withoutDup = (customers || []).filter(
    (c) => c.id !== newCustomer.id && !isWalkInCustomer(c)
  );
  const list = [newCustomer, ...withoutDup];
  return requireCustomer ? list : mergeCustomersWithWalkIn(list);
}

/** Prepend walk-in to the list if missing (avoid duplicate DB walk-in rows in picker). */
export function mergeCustomersWithWalkIn(customers = []) {
  const list = Array.isArray(customers) ? customers.filter((c) => !isWalkInCustomer(c)) : [];
  return [WALK_IN_CUSTOMER, ...list];
}

/** customer_id for API payloads — null for walk-in. */
export function customerIdForSale(customer) {
  if (!customer || isWalkInCustomer(customer)) return null;
  return customer.id;
}
