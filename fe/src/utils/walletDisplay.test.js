import {
  formatWalletBalanceLabel,
  getWalletCreditAmount,
  getWalletDebtAmount,
  parseWalletBalance,
  walletBalanceTone,
} from './walletDisplay';

describe('walletDisplay', () => {
  it('parses wallet balance safely', () => {
    expect(parseWalletBalance('50')).toBe(50);
    expect(parseWalletBalance('-25.5')).toBe(-25.5);
    expect(parseWalletBalance(undefined)).toBe(0);
    expect(parseWalletBalance('bad')).toBe(0);
  });

  it('extracts debt and credit amounts', () => {
    expect(getWalletDebtAmount(-120)).toBe(120);
    expect(getWalletDebtAmount(50)).toBe(0);
    expect(getWalletCreditAmount(80)).toBe(80);
    expect(getWalletCreditAmount(-10)).toBe(0);
  });

  it('formats labels and tones', () => {
    expect(formatWalletBalanceLabel(-100)).toMatch(/owed/);
    expect(formatWalletBalanceLabel(40)).toMatch(/credit/);
    expect(walletBalanceTone(-1)).toBe('debt');
    expect(walletBalanceTone(1)).toBe('credit');
    expect(walletBalanceTone(0)).toBe('neutral');
  });
});
