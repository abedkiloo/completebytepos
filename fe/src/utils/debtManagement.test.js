import {
  AGING_BUCKET_LABELS,
  emptyDebtSummary,
  walletTxnLabel,
  getTodayDateString,
  shiftDate,
  formatDateLabel,
  isPaymentsTrailTodayRange,
  paymentsTrailLast30DaysRange,
  paymentsTrailTodayRange,
  settlementMethodLabel,
  settlementPayerLabel,
  settlementReferenceLabel,
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

  it('paymentsTrailTodayRange sets from and to to the same day', () => {
    expect(paymentsTrailTodayRange('2026-11-14')).toEqual({
      dateFrom: '2026-11-14',
      dateTo: '2026-11-14',
    });
  });

  it('paymentsTrailLast30DaysRange ends today and starts 30 days earlier', () => {
    expect(paymentsTrailLast30DaysRange('2026-11-14')).toEqual({
      dateFrom: '2026-10-15',
      dateTo: '2026-11-14',
    });
  });

  it('isPaymentsTrailTodayRange is true only when both bounds are today', () => {
    expect(isPaymentsTrailTodayRange('2026-11-14', '2026-11-14', '2026-11-14')).toBe(true);
    expect(isPaymentsTrailTodayRange('2026-10-15', '2026-11-14', '2026-11-14')).toBe(false);
    expect(isPaymentsTrailTodayRange('', '2026-11-14', '2026-11-14')).toBe(false);
  });

  it('labels method with till/bank and payer', () => {
    expect(
      settlementMethodLabel({
        payment_method: 'mpesa',
        mpesa_destination: 'till',
      })
    ).toBe('M-PESA · Till');
    expect(
      settlementPayerLabel({
        payer_name: 'Ann',
        payer_phone: '0700',
      })
    ).toBe('Ann · 0700');
    expect(settlementReferenceLabel({ reference: 'QHX1' })).toBe('QHX1');
  });
});
