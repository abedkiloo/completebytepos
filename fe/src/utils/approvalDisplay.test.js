import {
  buildApprovalDiffRows,
  describeApprovalSummary,
  expenseApprovalDetails,
  formatActionTypeLabel,
  formatApprovalValue,
  formatEntityTypeLabel,
  formatFieldLabel,
} from './approvalDisplay';

describe('approvalDisplay', () => {
  test('formatActionTypeLabel maps known actions', () => {
    expect(formatActionTypeLabel('product_price')).toBe('Selling price change');
    expect(formatActionTypeLabel('stock_adjust')).toBe('Stock adjustment');
    expect(formatActionTypeLabel('sale_rollback')).toBe('Sale rollback');
    expect(formatActionTypeLabel('debt_collection')).toBe('Debt collection');
    expect(formatActionTypeLabel('sale_complete')).toBe('Sale completion');
    expect(formatActionTypeLabel('unknown_action')).toBe('unknown action');
  });

  test('formatEntityTypeLabel prefers entity_repr', () => {
    expect(formatEntityTypeLabel('products.Product', 'Blue Shirt')).toBe('Blue Shirt');
    expect(formatEntityTypeLabel('products.Product', '')).toBe('Product');
    expect(formatEntityTypeLabel('sales.Customer', '')).toBe('Customer');
  });

  test('formatFieldLabel humanizes keys', () => {
    expect(formatFieldLabel('stock_quantity')).toBe('Stock on hand');
    expect(formatFieldLabel('custom_field')).toBe('custom field');
  });

  test('formatApprovalValue formats money, booleans, and payment methods', () => {
    expect(formatApprovalValue('price', '1200')).toMatch(/1,?200/);
    expect(formatApprovalValue('is_active', false)).toBe('No');
    expect(formatApprovalValue('enabled_payment_methods', ['cash', 'mpesa'])).toBe(
      'Cash, M-Pesa'
    );
    expect(formatApprovalValue('payment_method', 'mpesa')).toBe('M-Pesa');
    expect(formatApprovalValue('tax_rate', '16')).toBe('16%');
  });

  test('buildApprovalDiffRows lists only changed fields', () => {
    const rows = buildApprovalDiffRows(
      { price: '100', stock_quantity: 5 },
      { price: '120', stock_quantity: 5 }
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].label).toBe('Selling price');
    expect(rows[0].before).toMatch(/100/);
    expect(rows[0].after).toMatch(/120/);
  });

  test('describeApprovalSummary builds headline', () => {
    const out = describeApprovalSummary({
      action_type: 'product_stock',
      entity_type: 'products.Product',
      entity_repr: 'Tee — Large / White',
    });
    expect(out.headline).toBe('Stock change — Tee — Large / White');
  });

  test('formatApprovalValue handles arrays and objects', () => {
    expect(formatApprovalValue('notes', ['a', 'b'])).toBe('a, b');
    expect(formatApprovalValue('permissions', { a: 1 })).toBe('{"a":1}');
    expect(formatApprovalValue('price', null)).toBe('—');
    expect(formatApprovalValue('unit', 'kg')).toBe('kg');
    expect(formatApprovalValue('payment_method', 'cheque')).toBe('cheque');
    expect(formatApprovalValue('tax_rate', 'n/a')).toBe('n/a');
    expect(formatApprovalValue('price', 'not-a-number')).toBe('not-a-number');
  });

  test('buildApprovalDiffRows returns empty when values match', () => {
    expect(buildApprovalDiffRows({ price: '10' }, { price: '10' })).toEqual([]);
  });

  test('expenseApprovalDetails builds filtered expense facts', () => {
    const details = expenseApprovalDetails({
      expense_number: 'EXP-9',
      amount: '2500',
      category_name: 'Rent',
      expense_date: '2026-10-01',
      payment_method: 'mpesa',
      vendor: 'Landlord Co',
      receipt_number: '',
      notes: 'October',
    });
    expect(details.sections).toHaveLength(1);
    expect(details.sections[0].title).toBe('Expense');
    const labels = details.sections[0].facts.map((fact) => fact.label);
    expect(labels).toEqual([
      'Reference',
      'Amount',
      'Category',
      'Expense date',
      'Payment method',
      'Vendor',
      'Notes',
    ]);
    expect(details.sections[0].facts.find((f) => f.label === 'Payment method').value).toBe(
      'M-PESA'
    );
    expect(expenseApprovalDetails({}).sections[0].facts).toEqual([]);
    expect(
      expenseApprovalDetails({ payment_method: 'wire' }).sections[0].facts[0]
    ).toEqual({ label: 'Payment method', value: 'wire' });
  });
});
