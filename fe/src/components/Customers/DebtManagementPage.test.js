import { emptyDebtSummary, walletTxnLabel, AGING_BUCKET_LABELS } from '../../utils/debtManagement';

/**
 * Smoke coverage for debt helpers used by DebtManagementPage.
 * Full page render is covered manually / via API tests.
 */
describe('DebtManagementPage helpers', () => {
  it('has aging labels used by the dashboard', () => {
    expect(Object.keys(AGING_BUCKET_LABELS)).toEqual(['0_7', '8_30', '31_60', '60_plus']);
  });

  it('starts from an empty summary shape', () => {
    expect(emptyDebtSummary().customers_with_debt).toBe(0);
  });

  it('labels settlement transactions', () => {
    expect(walletTxnLabel('debt_settlement')).toContain('Payment');
  });
});
