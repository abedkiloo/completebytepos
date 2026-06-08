import { PERSONA, resolvePersona, userMayEditFinancialFieldsFromStorage } from './roleAccess';
import { cacheModuleSettings } from './moduleSettingsCache';
import { cacheStoreSettings } from './storeSettingsCache';
import { salesShowDiscount } from './salesDisplay';
import { installLocalStorageMock } from '../test-utils';

describe('financial field access', () => {
  beforeEach(() => {
    installLocalStorageMock();
    localStorage.clear();
  });

  test('sales persona cannot edit financial fields', () => {
    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'cashier', custom_role: { name: 'Sales Personnel' } })
    );
    expect(resolvePersona({ profile: JSON.parse(localStorage.getItem('profile')) })).toBe(
      PERSONA.SALES
    );
    expect(userMayEditFinancialFieldsFromStorage()).toBe(false);
  });

  test('manager may edit financial fields', () => {
    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'manager', custom_role: { name: 'Manager' } })
    );
    cacheModuleSettings('products', {
      allow_manager_edit_pricing: true,
      allow_manager_edit_cost: false,
    });
    expect(userMayEditFinancialFieldsFromStorage()).toBe(true);
  });

  test('sales may edit financial fields when stock flag enabled', () => {
    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'cashier', custom_role: { name: 'Sales Personnel' } })
    );
    cacheModuleSettings('products', {
      allow_sales_catalog_access: true,
      allow_sales_edit_stock: true,
    });
    cacheStoreSettings({ allow_sales_add_products: true });
    expect(userMayEditFinancialFieldsFromStorage()).toBe(true);
  });

  test('sales cannot see discount controls even when module flag is on', () => {
    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'cashier', custom_role: { name: 'Sales Personnel' } })
    );
    expect(salesShowDiscount({ show_discount: { value: true } })).toBe(false);
  });
});
