import {
  userCanRefundSales,
  saleIsRefundable,
  buildFullRefundPayload,
  buildPartialRefundPayload,
  refundStatusLabel,
  handleSaleRefundResponse,
} from './saleRefund';

describe('saleRefund', () => {
  const refundPerm = [{ module: 'sales', action: 'refund', name: 'sales.refund' }];

  it('checks refund permission', () => {
    expect(userCanRefundSales(refundPerm)).toBe(true);
    expect(userCanRefundSales([], { isManagerOrAdmin: true })).toBe(true);
    expect(userCanRefundSales([])).toBe(false);
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
