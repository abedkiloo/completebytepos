import {
  buildSaleCommitSummary,
  saleCommitConfirmLabel,
  saleCommitTitle,
} from './saleCommitSummary';

describe('saleCommitSummary', () => {
  test('builds a full-payment summary with change', () => {
    expect(
      buildSaleCommitSummary({
        total: 100,
        received: 150,
        paymentMethod: 'cash',
        itemCount: 3,
        customerName: 'Ada',
      })
    ).toEqual({
      total: 100,
      received: 150,
      change: 50,
      balance: 0,
      paymentMethod: 'cash',
      itemCount: 3,
      customerName: 'Ada',
      paymentReference: '',
      kind: 'full',
    });
    expect(saleCommitTitle('full')).toBe('Confirm sale?');
    expect(saleCommitConfirmLabel('full')).toBe('Confirm & complete sale');
  });

  test('builds partial and pay-later kinds', () => {
    expect(buildSaleCommitSummary({ total: 200, received: 50 }).kind).toBe('partial');
    expect(buildSaleCommitSummary({ total: 200, received: 0 }).kind).toBe('pay_later');
    expect(saleCommitConfirmLabel('partial')).toBe('Confirm sale & debt');
    expect(saleCommitConfirmLabel('pay_later')).toBe('Confirm — pay later');
    expect(saleCommitTitle('partial')).toBe('Confirm partial payment?');
    expect(saleCommitTitle('pay_later')).toBe('Confirm pay-later sale?');
  });

  test('normalizes empty defaults and invalid numbers', () => {
    expect(buildSaleCommitSummary()).toEqual({
      total: 0,
      received: 0,
      change: 0,
      balance: 0,
      paymentMethod: 'cash',
      itemCount: 0,
      customerName: null,
      paymentReference: '',
      kind: 'full',
    });
    expect(
      buildSaleCommitSummary({
        total: 'abc',
        received: null,
        paymentMethod: null,
        itemCount: 'x',
        customerName: '',
        paymentReference: '  REF  ',
      })
    ).toEqual({
      total: 0,
      received: 0,
      change: 0,
      balance: 0,
      paymentMethod: 'cash',
      itemCount: 0,
      customerName: null,
      paymentReference: 'REF',
      kind: 'full',
    });
  });

  test('unknown kind labels fall back to full-sale copy', () => {
    expect(saleCommitConfirmLabel('other')).toBe('Confirm & complete sale');
    expect(saleCommitTitle('other')).toBe('Confirm sale?');
    expect(saleCommitConfirmLabel()).toBe('Confirm & complete sale');
    expect(saleCommitTitle()).toBe('Confirm sale?');
  });
});
