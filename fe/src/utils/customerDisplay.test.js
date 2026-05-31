import {
  customersShowCustomerCode,
  customersShowOutstandingBalance,
  customersEnableCreate,
  customersShowStatus,
  customersAllowQuickAddAtPos,
} from './customerDisplay';

describe('customerDisplay', () => {
  test('defaults are enabled', () => {
    expect(customersShowCustomerCode({})).toBe(true);
    expect(customersShowOutstandingBalance({})).toBe(true);
    expect(customersEnableCreate({})).toBe(true);
    expect(customersAllowQuickAddAtPos({})).toBe(true);
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
});
