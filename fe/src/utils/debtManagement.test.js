import {
  AGING_BUCKET_LABELS,
  emptyDebtSummary,
  walletTxnLabel,
} from './debtManagement';

describe('debtManagement utils', () => {
  it('provides aging labels for all buckets', () => {
    expect(AGING_BUCKET_LABELS['0_7']).toMatch(/0/);
    expect(AGING_BUCKET_LABELS['60_plus']).toMatch(/60/);
  });

  it('emptyDebtSummary has zeroed cards and aging', () => {
    const empty = emptyDebtSummary();
    expect(empty.customers_with_debt).toBe(0);
    expect(empty.aging['8_30'].count).toBe(0);
  });

  it('maps wallet source types to readable labels', () => {
    expect(walletTxnLabel('debt_settlement')).toBe('Payment received');
    expect(walletTxnLabel('debt')).toBe('Debt added');
  });
});
