import {
  customerDetailPath,
  formatDebtTrail,
  formatSettlementMeta,
  ledgerSourceLabel,
  standingLabel,
} from './customerDetail';

describe('customerDetail helpers', () => {
  it('formats settlement debt trail previous → paid → new', () => {
    expect(
      formatDebtTrail({
        previous_debt: '600.00',
        payment_amount: '300.00',
        new_debt: '300.00',
      })
    ).toBe('Previous debt 600.00 · Paid 300.00 · New debt 300.00');
  });

  it('formats sale debt trail with paid amount', () => {
    expect(
      formatDebtTrail({
        previous_debt: '0.00',
        sale_total: '630.00',
        sale_paid: '330.00',
        debt_added: '300.00',
        new_debt: '300.00',
      })
    ).toContain('Sale 630.00 · paid 330.00');
  });

  it('labels ledger sources and standing', () => {
    expect(ledgerSourceLabel('debt_settlement')).toBe('Debt payment');
    expect(ledgerSourceLabel('debt')).toBe('Sale debt');
    expect(standingLabel('debt')).toBe('Has debt');
    expect(standingLabel('credit')).toBe('Has credit');
    expect(standingLabel('good')).toBe('Clear');
  });

  it('builds detail paths with optional ledger tab', () => {
    expect(customerDetailPath(12)).toBe('/customers/12');
    expect(customerDetailPath(12, { tab: 'ledger' })).toBe('/customers/12?tab=ledger');
  });

  it('formats settlement meta with method, reference, and collector', () => {
    expect(
      formatSettlementMeta({
        source_type: 'debt_settlement',
        payment_method: 'mpesa',
        payment_method_label: 'M-PESA',
        reference: 'QHX7K2L9M1',
        created_by_name: 'manager',
      })
    ).toBe('M-PESA · Ref QHX7K2L9M1 · Recorded by manager');
    expect(
      formatSettlementMeta({
        source_type: 'debt_settlement',
        payment_method: 'cash',
        payment_method_label: 'Cash',
        created_by_name: 'cashier1',
      })
    ).toBe('Cash · Collected by cashier1');
    expect(formatSettlementMeta({ source_type: 'debt' })).toBe('');
  });
});
