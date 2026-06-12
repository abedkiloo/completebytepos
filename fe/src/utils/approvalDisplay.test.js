import {
  buildApprovalDiffRows,
  describeApprovalSummary,
  formatActionTypeLabel,
  formatApprovalValue,
  formatEntityTypeLabel,
  formatFieldLabel,
} from './approvalDisplay';

describe('approvalDisplay', () => {
  test('formatActionTypeLabel maps known actions', () => {
    expect(formatActionTypeLabel('product_price')).toBe('Selling price change');
    expect(formatActionTypeLabel('stock_adjust')).toBe('Stock adjustment');
    expect(formatActionTypeLabel('unknown_action')).toBe('unknown action');
  });

  test('formatEntityTypeLabel prefers entity_repr', () => {
    expect(formatEntityTypeLabel('products.Product', 'Blue Shirt')).toBe('Blue Shirt');
    expect(formatEntityTypeLabel('products.Product', '')).toBe('Product');
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
  });

  test('buildApprovalDiffRows returns empty when values match', () => {
    expect(buildApprovalDiffRows({ price: '10' }, { price: '10' })).toEqual([]);
  });
});
