import {
  formatInvoiceItemsForApi,
  formatPaymentPayload,
  resolveLineProductId,
} from './invoicePayload';

describe('invoicePayload', () => {
  test('resolveLineProductId prefers product_id', () => {
    expect(resolveLineProductId({ product_id: 5, product: 9 })).toBe(5);
  });

  test('resolveLineProductId accepts product alias', () => {
    expect(resolveLineProductId({ product: '12' })).toBe(12);
  });

  test('formatInvoiceItemsForApi emits product_id', () => {
    const rows = formatInvoiceItemsForApi([
      { product: 3, quantity: '2', unit_price: '10' },
    ]);
    expect(rows).toEqual([
      {
        product_id: 3,
        quantity: 2,
        unit_price: 10,
        description: '',
        variant_id: null,
      },
    ]);
  });

  test('formatPaymentPayload uses invoice_id', () => {
    expect(
      formatPaymentPayload({
        invoiceId: 7,
        amount: '50',
        payment_method: 'cash',
        payment_date: '2026-05-31',
        reference: 'R1',
        notes: 'n',
      })
    ).toMatchObject({
      invoice_id: 7,
      amount: 50,
      payment_method: 'cash',
    });
  });
});
