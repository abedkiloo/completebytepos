import {
  customersShowCustomerCode,
  customersShowOutstandingBalance,
  customersEnableCreate,
  customersEnableEdit,
  customersShowStatus,
  customersAllowQuickAddAtPos,
  canQuickAddCustomerAtPos,
  canEditCustomer,
  customerHasLocationPing,
  customerMapsUrl,
  formatCustomerLocationPing,
  formatCustomerPlaceLine,
} from './customerDisplay';

describe('customerDisplay', () => {
  test('defaults are enabled', () => {
    expect(customersShowCustomerCode({})).toBe(true);
    expect(customersShowOutstandingBalance({})).toBe(true);
    expect(customersEnableCreate({})).toBe(true);
    expect(customersEnableEdit({})).toBe(true);
    expect(customersAllowQuickAddAtPos({})).toBe(true);
  });

  test('canEditCustomer requires store flag plus create or update (or manager)', () => {
    expect(canEditCustomer({ enable_customer_edit: false }, [{ module: 'customers', action: 'update' }])).toBe(false);
    expect(canEditCustomer({ enable_customer_edit: true }, [])).toBe(false);
    expect(
      canEditCustomer({ enable_customer_edit: true }, [{ module: 'customers', action: 'create' }])
    ).toBe(true);
    expect(
      canEditCustomer({ enable_customer_edit: true }, [{ name: 'customers.update' }])
    ).toBe(true);
    expect(canEditCustomer({ enable_customer_edit: true }, [], { isManagerOrAdmin: true })).toBe(true);
  });

  test('show_customer_status respects store hide_entity_status_toggles', () => {
    expect(customersShowStatus({ show_customer_status: true }, {})).toBe(true);
    expect(
      customersShowStatus({ show_customer_status: true }, { hide_entity_status_toggles: true })
    ).toBe(false);
  });

  test('quick add requires create enabled', () => {
    expect(
      customersAllowQuickAddAtPos({
        allow_quick_add_at_pos: true,
        enable_customer_create: false,
      })
    ).toBe(false);
  });

  test('canQuickAddCustomerAtPos allows sales staff with customers.create', () => {
    const settings = { allow_quick_add_at_pos: true, enable_customer_create: true };
    expect(canQuickAddCustomerAtPos(false, settings, [])).toBe(false);
    expect(
      canQuickAddCustomerAtPos(false, settings, [{ module: 'customers', action: 'create' }])
    ).toBe(true);
    expect(canQuickAddCustomerAtPos(true, settings, [])).toBe(true);
  });

  test('formats snapped GPS pin and place line for customer details', () => {
    expect(customerHasLocationPing({})).toBe(false);
    expect(customerHasLocationPing({ latitude: -1.2921, longitude: 36.8219 })).toBe(true);
    expect(formatCustomerLocationPing({ latitude: -1.2921, longitude: 36.8219 })).toBe(
      '-1.29210, 36.82190'
    );
    expect(customerMapsUrl({ latitude: -1.2921, longitude: 36.8219 })).toBe(
      'https://maps.google.com/?q=-1.2921,36.8219'
    );
    expect(
      formatCustomerPlaceLine({
        address: 'Near stage',
        ward: 'Kilimani',
        sub_county: 'Westlands',
        county: 'Nairobi',
        country: 'Kenya',
      })
    ).toBe('Near stage · Kilimani, Westlands, Nairobi · Kenya');
    expect(formatCustomerPlaceLine({})).toBe('');
    expect(customerMapsUrl({ latitude: 'bad', longitude: 36 })).toBeNull();
  });
});
