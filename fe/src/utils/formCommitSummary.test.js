import {
  compactCommitRows,
  userCommitRows,
  assignRoleRows,
  invoiceCommitRows,
  invoiceSendRows,
  settingsCommitRows,
  roleCommitRows,
  branchCommitRows,
  employeeCommitRows,
  customerCommitRows,
  supplierCommitRows,
  productCommitRows,
  categoryCommitRows,
  moduleToggleRows,
  attributeDeleteRows,
  approvalCommitRows,
  installCommitRows,
  expenseCategoryCommitRows,
  attributeSaveRows,
  presetApplyRows,
  featureToggleRows,
  approvalExpenseRows,
  saleRollbackRows,
} from './formCommitSummary';

describe('formCommitSummary', () => {
  test('compactCommitRows drops empty values', () => {
    expect(compactCommitRows()).toEqual([]);
    expect(compactCommitRows(null)).toEqual([]);
    expect(
      compactCommitRows([
        null,
        { label: null, value: 'x' },
        { label: 'A', value: null },
        { label: 'B', value: '' },
        { label: 'C', value: '1' },
      ]),
    ).toEqual([{ label: 'C', value: '1' }]);
  });

  test('entity row builders cover create, edit, and fallbacks', () => {
    expect(userCommitRows().find((r) => r.label === 'Username').value).toBe('—');
    expect(userCommitRows({ username: 'ada', first_name: 'Ada', last_name: 'K', email: 'a@b.c', role: 'cashier' })[0].value).toBe('ada');
    expect(userCommitRows({}, { isEdit: true }).find((r) => r.label === 'Action').value).toBe('Update user');
    expect(assignRoleRows().find((r) => r.label === 'New role').value).toBe('—');
    expect(assignRoleRows({ username: 'bob' }, 'Manager')[1].value).toBe('Manager');
    expect(invoiceCommitRows().find((r) => r.label === 'Customer').value).toBe('Walk-in');
    expect(invoiceCommitRows({ items: [{ product_id: 1 }, {}], total: 10 }, { formatMoney: (n) => `K${n}` })
      .find((r) => r.label === 'Total').value).toBe('K10');
    expect(invoiceCommitRows({ customer_name: 'Ada' }, { isEdit: true }).find((r) => r.label === 'Action').value)
      .toBe('Update invoice');
    expect(invoiceSendRows()[0].value).toBe('—');
    expect(invoiceSendRows({ id: 4, total: 9 }, (n) => String(n))[0].value).toBe('#4');
    expect(invoiceSendRows({ invoice_number: 'INV-1', customer_name: 'Ada' })[0].value).toBe('INV-1');
    expect(settingsCommitRows({}, { clearingLogo: true })[0].value).toBe('Remove receipt logo');
    expect(settingsCommitRows({ a: 1 }, { hasLogo: true }).find((r) => r.label === 'Receipt logo').value)
      .toContain('uploaded');
    expect(settingsCommitRows().find((r) => r.label === 'Changes').value).toBe('No field changes');
    expect(settingsCommitRows(null).find((r) => r.label === 'Changes').value).toBe('No field changes');
    expect(roleCommitRows().find((r) => r.label === 'Role').value).toBe('—');
    expect(roleCommitRows({ name: 'Cashier', permission_ids: [1, 2] }, { isEdit: true })[1].value).toBe('2');
    expect(branchCommitRows()).toHaveLength(2);
    expect(branchCommitRows({ name: 'HQ', branch_code: 'NBO', city: 'Nairobi' }, { isEdit: true })).toHaveLength(4);
    expect(employeeCommitRows()[0].value).toBe('—');
    expect(employeeCommitRows({ first_name: 'Ann', last_name: 'K', employee_id: 'E1', position: 'Cashier' }, { isEdit: true })[0].value)
      .toBe('Ann K');
    expect(customerCommitRows()[0].value).toBe('—');
    expect(customerCommitRows({ name: 'Ada', phone: '07', email: 'a@b.c' }, { isEdit: true }).find((r) => r.label === 'Phone').value).toBe('07');
    expect(supplierCommitRows()[0].value).toBe('—');
    expect(supplierCommitRows({ name: 'Acme', phone: '07' }, { isEdit: true }).find((r) => r.label === 'Action').value)
      .toBe('Update supplier');
    expect(productCommitRows()[1].value).toBe('0');
    expect(productCommitRows({ name: 'Tee', has_variants: true }, { isEdit: true })[1].value).toBe('With variants');
    expect(productCommitRows({ name: 'Nail', selling_price: 10 })[1].value).toBe('10');
    expect(productCommitRows({ price: 8 })[1].value).toBe('8');
    expect(categoryCommitRows()[0].label).toBe('Category');
    expect(categoryCommitRows({ name: 'Soda', description: 'Cold' }, { isSubcategory: true })[0].label).toBe('Subcategory');
    expect(moduleToggleRows()[1].value).toBe('Disabled');
    expect(moduleToggleRows({ module_name: 'pos' }, true)[1].value).toBe('Enabled');
    expect(moduleToggleRows({ module_name_display: 'POS' }, false)[1].value).toBe('Disabled');
    expect(attributeDeleteRows()[0].label).toBe('Size');
    expect(attributeDeleteRows({ name: 'Large' }, 'sizes')[0].label).toBe('Size');
    expect(attributeDeleteRows({ name: 'Blue' }, 'colors')[0].label).toBe('Color');
    expect(approvalCommitRows()[0].value).toBe('Pending change');
    expect(approvalCommitRows({ action_type: 'product_price', reason: 'ok' })[2].value)
      .toContain('Approve');
    expect(installCommitRows()[2].value).toBe('Not included');
    expect(installCommitRows({ preset: 'retail', includeTestData: true })[2].value).toBe('Included');
    expect(expenseCategoryCommitRows()[0].value).toBe('—');
    expect(expenseCategoryCommitRows({ name: 'Rent', description: 'Shop' }, { isEdit: true })[2].value)
      .toBe('Update category');
    expect(attributeSaveRows()[0].label).toBe('Size');
    expect(attributeSaveRows({ name: 'XL' }, { kind: 'sizes' })[0].label).toBe('Size');
    expect(attributeSaveRows({ name: 'Red' }, { kind: 'colors', isEdit: true })[1].value).toBe('Update');
    expect(presetApplyRows()[0].value).toBe('—');
    expect(presetApplyRows({ label: 'Retail starter' })[0].value).toBe('Retail starter');
    expect(presetApplyRows({ id: 'retail_full' })[0].value).toBe('retail_full');
    expect(featureToggleRows()[1].value).toBe('Off');
    expect(featureToggleRows({ feature_name: 'POS' }, true)[1].value).toBe('On');
    expect(approvalExpenseRows()[0].value).toBe('—');
    expect(approvalExpenseRows({ description: 'Fuel', amount: 20 })[0].value).toBe('Fuel');
    expect(approvalExpenseRows({ expense_number: 'EXP-1' })[0].value).toBe('EXP-1');
    expect(saleRollbackRows()[0].value).toBe('—');
    expect(saleRollbackRows({ sale_number: 'S-1', total: 100 }, 'wrong till')[2].value).toContain(
      'admin approval'
    );
  });
});
