import {
  saleAmountRefunded,
  saleBalanceDue,
  saleDisplayTotal,
  saleFinalStatusLabel,
  saleHasRefundActivity,
  saleItemNetQuantity,
  saleItemNetSubtotal,
  saleItemRefundableQuantity,
  saleItemVariantLabel,
  saleNetItemCount,
  saleNetTotal,
  salePaymentStatusLabel,
  normalizeSaleForReceipt,
  saleNetBalanceDue,
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

  it('computes net quantities, totals, and final status after refunds', () => {
    const item = { quantity: 3, quantity_refunded: 1, unit_price: '100', subtotal: '300' };
    expect(saleItemNetQuantity(item)).toBe(2);
    expect(saleItemNetSubtotal(item)).toBe(200);

    const sale = {
      total: '1000',
      amount_refunded: '200',
      refund_status: 'partial',
      items: [
        { quantity: 2, quantity_refunded: 1, unit_price: '500' },
        { quantity: 1, quantity_refunded: 0, unit_price: '100' },
      ],
    };
    expect(saleAmountRefunded(sale)).toBe(200);
    expect(saleNetTotal(sale)).toBe(800);
    expect(saleNetItemCount(sale)).toBe(2);
    expect(saleHasRefundActivity(sale)).toBe(true);
    expect(saleDisplayTotal(sale)).toBe(800);
    expect(saleFinalStatusLabel(sale)).toBe('Partial refund');
    expect(saleFinalStatusLabel({ ...sale, refund_status: 'refunded', amount_refunded: '1000' })).toBe(
      'Fully refunded'
    );
  });

  it('normalizes receipt data: drops zero-qty lines and hides refund history', () => {
    const sale = {
      total: '1000',
      subtotal: '1000',
      tax_amount: '0',
      discount_amount: '0',
      amount_paid: '1000',
      amount_refunded: '500',
      refund_status: 'partial',
      items: [
        { id: 1, product_name: 'A', quantity: 2, quantity_refunded: 2, unit_price: '250' },
        { id: 2, product_name: 'B', quantity: 1, quantity_refunded: 0, unit_price: '500' },
      ],
    };
    const receipt = normalizeSaleForReceipt(sale);
    expect(receipt.items).toHaveLength(1);
    expect(receipt.items[0].product_name).toBe('B');
    expect(receipt.items[0].quantity).toBe(1);
    expect(receipt.total).toBe(500);
    expect(receipt.subtotal).toBe(500);
    expect(saleNetBalanceDue(sale)).toBe(0);
  });
});
