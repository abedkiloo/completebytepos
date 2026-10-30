import {
  userCanRefundSales,
  userCanRollbackSales,
  userCanUnvoidSales,
  saleIsRefundable,
  saleIsRollbackable,
  saleIsUnvoidable,
  buildFullRefundPayload,
  buildRollbackPayload,
  buildPartialRefundPayload,
  refundStatusLabel,
  handleSaleRefundResponse,
} from './saleRefund';

describe('saleRefund', () => {
  const refundPerm = [{ module: 'sales', action: 'refund', name: 'sales.refund' }];
  const approvePerm = [{ module: 'sales', action: 'approve', name: 'sales.approve' }];

  it('checks refund permission — managers no longer get an automatic pass', () => {
    expect(userCanRefundSales(refundPerm)).toBe(true);
    expect(userCanRefundSales([], { isAdmin: true })).toBe(true);
    expect(userCanRefundSales([], { isManagerOrAdmin: true })).toBe(false);
    expect(userCanRefundSales([])).toBe(false);
  });

  it('checks unvoid permission (grantable) or admin override', () => {
    const unvoidPerm = [{ module: 'sales', action: 'unvoid', name: 'sales.unvoid' }];
    expect(userCanUnvoidSales(approvePerm)).toBe(false);
    expect(userCanUnvoidSales(unvoidPerm)).toBe(true);
    expect(userCanUnvoidSales([], { isAdmin: true })).toBe(true);
    expect(userCanUnvoidSales([])).toBe(false);
    expect(saleIsUnvoidable({ status: 'completed', refund_status: 'refunded' })).toBe(true);
    expect(saleIsUnvoidable({ status: 'cancelled' })).toBe(true);
    expect(saleIsUnvoidable({ status: 'completed', refund_status: 'none' })).toBe(false);
  });

  it('checks rollback only from the explicit permission', () => {
    const rollbackPerm = [{ module: 'sales', action: 'rollback', name: 'sales.rollback' }];
    expect(userCanRollbackSales(rollbackPerm)).toBe(true);
    expect(userCanRollbackSales([])).toBe(false);
    expect(userCanRollbackSales(refundPerm)).toBe(false);
  });

  it('detects rollbackable completed sales', () => {
    expect(saleIsRollbackable({ status: 'completed', refund_status: 'none' })).toBe(true);
    expect(saleIsRollbackable({ status: 'completed' })).toBe(true);
    expect(saleIsRollbackable({ status: 'completed', can_rollback: false })).toBe(false);
    expect(saleIsRollbackable({ status: 'completed', refund_status: 'partial' })).toBe(false);
    expect(saleIsRollbackable({ status: 'holding' })).toBe(false);
    expect(saleIsRollbackable(null)).toBe(false);
  });

  it('detects refundable completed sales', () => {
    expect(
      saleIsRefundable({
        status: 'completed',
        refund_status: 'none',
        refundable_remaining: '50',
      })
    ).toBe(true);
    expect(
      saleIsRefundable({ status: 'completed', refund_status: 'refunded' })
    ).toBe(false);
    expect(saleIsRefundable({ status: 'holding' })).toBe(false);
  });

  it('builds refund payloads', () => {
    expect(buildFullRefundPayload('  Customer return  ')).toEqual({
      full: true,
      reason: 'Customer return',
    });
    expect(buildRollbackPayload('  duplicate till  ')).toEqual({
      reason: 'duplicate till',
    });
    expect(
      buildPartialRefundPayload('Damaged', [{ id: 3, quantity: 1 }])
    ).toEqual({
      full: false,
      reason: 'Damaged',
      items: [{ sale_item_id: 3, quantity: 1 }],
    });
  });

  it('maps refund status labels', () => {
    expect(refundStatusLabel('refunded')).toBe('Refunded');
    expect(refundStatusLabel('partial')).toBe('Partial refund');
    expect(refundStatusLabel('none')).toBeNull();
  });

  it('handles immediate vs pending refund API responses', () => {
    const onApplied = jest.fn();
    const onPending = jest.fn();
    expect(
      handleSaleRefundResponse(
        { status: 201, data: { refund_number: 'RF-1' } },
        { onApplied, onPending }
      )
    ).toBe('applied');
    expect(onApplied).toHaveBeenCalledWith({ refund_number: 'RF-1' });

    onApplied.mockClear();
    expect(
      handleSaleRefundResponse(
        { status: 202, data: { pending_change: { id: 9 } } },
        { onApplied, onPending }
      )
    ).toBe('pending');
    expect(onPending).toHaveBeenCalled();
    expect(onApplied).not.toHaveBeenCalled();
  });
});
