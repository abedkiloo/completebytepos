import {
  AGING_BUCKET_LABELS,
  emptyDebtSummary,
  walletTxnLabel,
  getTodayDateString,
  shiftDate,
  formatDateLabel,
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

  it('shifts collection dates across month boundaries', () => {
    expect(shiftDate('2026-09-12', 1)).toBe('2026-09-13');
    expect(shiftDate('2026-03-01', -1)).toBe('2026-02-28');
  });

  it('labels today in formatDateLabel', () => {
    const today = getTodayDateString();
    expect(formatDateLabel(today)).toContain('Today');
  });
});
