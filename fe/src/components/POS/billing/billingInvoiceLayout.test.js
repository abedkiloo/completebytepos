import {
  BILLING_AMOUNT_RECEIVED_CLASS,
  BILLING_INVOICE_CARD_CLASS,
  BILLING_PARTIAL_PAYMENT_BLOCK_CLASS,
  BILLING_PAYMENT_SECTION_CLASS,
  BILLING_RIGHT_COLUMN_CLASS,
  BILLING_TOTALS_SECTION_CLASS,
} from './billingInvoiceLayout';

describe('billingInvoiceLayout', () => {
  it('reserves vertical spacing between payment block and amount received', () => {
    expect(BILLING_PAYMENT_SECTION_CLASS).toMatch(/space-y-4/);
    expect(BILLING_AMOUNT_RECEIVED_CLASS).toMatch(/space-y-2/);
    expect(BILLING_PARTIAL_PAYMENT_BLOCK_CLASS).toMatch(/py-3/);
  });

  it('allows the right column to scroll instead of clipping content', () => {
    expect(BILLING_RIGHT_COLUMN_CLASS).toMatch(/overflow-y-auto/);
    expect(BILLING_RIGHT_COLUMN_CLASS).toMatch(/max-h-/);
  });

  it('separates totals from payment controls', () => {
    expect(BILLING_TOTALS_SECTION_CLASS).toMatch(/mt-4/);
    expect(BILLING_TOTALS_SECTION_CLASS).toMatch(/border-t/);
    expect(BILLING_INVOICE_CARD_CLASS).not.toMatch(/flex-1/);
  });
});
