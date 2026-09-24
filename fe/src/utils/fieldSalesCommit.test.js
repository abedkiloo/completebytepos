import {
  assignCommitRows,
  assignDriverError,
  canAssignDriver,
  canMarkReady,
  deliveryAssigneeLabel,
  fieldOrderLineSummary,
  fieldOrderQty,
  fieldOrderTotal,
  packCommitRows,
  packReadyError,
} from './fieldSalesCommit';

const submitted = {
  id: 44,
  status: 'submitted',
  customer_name: 'Ada',
  lines: [
    { product_id: 1, product_name: 'Cement', quantity: 2, unit_price: 150, line_total: 300 },
    { product_id: 2, product_name: 'Sand', quantity: 1, unit_price: 80 },
    { product_id: 3, quantity: 1, unit_price: 10 },
  ],
};

describe('fieldSalesCommit', () => {
  test('summarizes qty, totals, and truncated product names', () => {
    expect(fieldOrderQty(submitted)).toBe(4);
    expect(fieldOrderTotal(submitted)).toBe(390);
    expect(fieldOrderLineSummary(submitted)).toContain('Cement, Sand +1');
    expect(fieldOrderQty()).toBe(0);
    expect(fieldOrderTotal()).toBe(0);
    expect(fieldOrderLineSummary({ lines: [{ product_id: 9, quantity: 1 }] })).toBe(
      'Product #9 · qty 1',
    );
    expect(fieldOrderTotal({ lines: [{ quantity: 0, unit_price: 0, line_total: null }] })).toBe(0);
    expect(packCommitRows({}).find((row) => row.label === 'Order').value).toBe('');
    expect(assignCommitRows({}, { username: '' }).find((row) => row.label === 'Order').value).toBe('');
    expect(canMarkReady({ status: 'packing' })).toBe(true);
    expect(canAssignDriver({ status: 'packing' })).toBe(true);
    expect(fieldOrderLineSummary({ lines: [] })).toBe('—');
    expect(fieldOrderTotal({ lines: [{ quantity: 'x', unit_price: 'y' }] })).toBe(0);
    expect(fieldOrderTotal({ lines: [{ quantity: 2, unit_price: 5 }] })).toBe(10);
  });

  test('pack and assign eligibility', () => {
    expect(canMarkReady(submitted)).toBe(true);
    expect(canMarkReady({ status: 'ready' })).toBe(false);
    expect(canAssignDriver({ status: 'ready' })).toBe(true);
    expect(canAssignDriver({ status: 'ready', assigned_delivery_agent_id: 9 })).toBe(false);
    expect(canAssignDriver({ status: 'submitted' })).toBe(false);
  });

  test('packReadyError covers permission, missing order, status, and empty cart', () => {
    expect(packReadyError(submitted, false)).toBe('You cannot pack this order.');
    expect(packReadyError(null)).toBe('Select an order first.');
    expect(packReadyError({ status: 'ready', lines: submitted.lines })).toBe(
      'This order is not waiting to be packed.',
    );
    expect(packReadyError({ status: 'submitted', lines: [] })).toBe(
      'This order has no products to pack.',
    );
    expect(packReadyError(submitted)).toBe('');
  });

  test('assignDriverError covers permission, status, and missing driver', () => {
    expect(assignDriverError(submitted, 3, false)).toBe('You cannot assign this delivery.');
    expect(assignDriverError(null, 3)).toBe('Select an order first.');
    expect(assignDriverError(submitted, 3)).toBe('This order is not ready to assign.');
    expect(assignDriverError({ status: 'ready' }, '')).toBe('Select who will deliver first.');
    expect(assignDriverError({ status: 'ready' }, 8)).toBe('');
  });

  test('commit rows include summary and driver fallbacks', () => {
    const packed = packCommitRows(submitted, (n) => `KES ${n}`);
    expect(packed.find((row) => row.label === 'Order').value).toBe('#44');
    expect(packed.find((row) => row.label === 'Total').value).toBe('KES 390');

    const noFormatter = packCommitRows({ id: 1, customer_name: '', lines: [] });
    expect(noFormatter.find((row) => row.label === 'Customer').value).toBe('—');
    expect(noFormatter.find((row) => row.label === 'Total').value).toBe('0');

    expect(assignCommitRows(submitted, { display_name: 'Jane' }, (n) => String(n))
      .find((row) => row.label === 'Delivered by').value).toBe('Jane');
    expect(assignCommitRows(submitted, { username: 'bob' })
      .find((row) => row.label === 'Delivered by').value).toBe('bob');
    expect(assignCommitRows(submitted, null)
      .find((row) => row.label === 'Delivered by').value).toBe('Selected person');
    expect(assignCommitRows(submitted, { display_name: 'Ada', role_name: 'Sales Personnel' })
      .find((row) => row.label === 'Delivered by').value).toBe('Ada · Sales Personnel');
  });

  test('deliveryAssigneeLabel covers name, role, and id fallbacks', () => {
    expect(deliveryAssigneeLabel({ display_name: 'Jane', role_name: 'Delivery Driver' }))
      .toBe('Jane · Delivery Driver');
    expect(deliveryAssigneeLabel({ username: 'bob' })).toBe('bob');
    expect(deliveryAssigneeLabel({ role_name: 'Sales Personnel' })).toBe('Sales Personnel');
    expect(deliveryAssigneeLabel({ id: 7 })).toBe('Person #7');
    expect(deliveryAssigneeLabel(null)).toBe('Selected person');
  });
});
