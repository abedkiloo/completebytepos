import { suppliersShowCreditFields, suppliersShowStatus } from './supplierDisplay';

describe('supplierDisplay', () => {
  test('credit fields default on', () => {
    expect(suppliersShowCreditFields({})).toBe(true);
  });

  test('status respects hide_entity_status_toggles', () => {
    expect(
      suppliersShowStatus({ show_supplier_status: true }, { hide_entity_status_toggles: true })
    ).toBe(false);
  });
});
