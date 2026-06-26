import {
  saleBalanceDue,
  saleItemRefundableQuantity,
  saleItemVariantLabel,
  salePaymentStatusLabel,
} from './saleItemDisplay';

describe('saleItemDisplay', () => {
  it('formats variant label from size and color', () => {
    expect(
      saleItemVariantLabel({
        size_name: 'Large',
        color_name: 'White',
      })
    ).toBe('Large / White');
  });

  it('computes refundable quantity from refunded amount', () => {
    expect(
      saleItemRefundableQuantity({ quantity: 3, quantity_refunded: 1 })
    ).toBe(2);
    expect(saleItemRefundableQuantity({ quantity: 2, refundable_quantity: 2 })).toBe(2);
  });

  it('computes balance due and payment status', () => {
    const sale = { total: '1000', amount_paid: '600' };
    expect(saleBalanceDue(sale)).toBe(400);
    expect(salePaymentStatusLabel(sale)).toBe('Partial payment');
    expect(salePaymentStatusLabel({ total: '100', amount_paid: '100' })).toBe('Paid in full');
    expect(salePaymentStatusLabel({ total: '100', amount_paid: '0' })).toBe('Unpaid');
    expect(saleBalanceDue({ total: '100', amount_paid: '100' })).toBe(0);
  });

  it('returns zero refundable when line fully refunded', () => {
    expect(
      saleItemRefundableQuantity({ quantity: 2, quantity_refunded: 2, refundable_quantity: 0 })
    ).toBe(0);
  });
});
