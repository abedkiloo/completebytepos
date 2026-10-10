import {
  formatCurrency,
  formatDate,
  formatDateTime,
  formatNumber,
  formatCompactNumber,
  formatCompactCurrency,
} from './formatters';

describe('formatters', () => {
  it('formatCurrency handles null as zero', () => {
    expect(formatCurrency(null)).toMatch(/0\.00/);
  });

  it('formatDate returns empty for falsy', () => {
    expect(formatDate(null)).toBe('');
  });

  it('formatDate formats ISO strings', () => {
    expect(formatDate('2024-06-15')).toMatch(/2024/);
  });

  it('formatDateTime formats a known date', () => {
    const s = formatDateTime('2024-06-15T14:30:00');
    expect(s).toContain('2024');
    expect(s).toMatch(/PM|AM/);
  });

  it('formatNumber uses locale grouping', () => {
    expect(formatNumber(1000)).toBe('1,000');
  });

  it('formatCompactNumber groups below 1M and scales M', () => {
    expect(formatCompactNumber(500)).toBe('500');
    expect(formatCompactNumber(1500)).toBe('1,500');
    expect(formatCompactNumber(2_000_000)).toBe('2.0M');
    expect(formatCompactNumber(0)).toBe('0');
    expect(formatCompactNumber(-2500)).toBe('-2,500');
  });

  it('formatCompactCurrency groups below 1M and scales M', () => {
    expect(formatCompactCurrency(5000)).toMatch(/5,000/);
    expect(formatCompactCurrency(0)).toMatch(/0\.00/);
    expect(formatCompactCurrency(2_000_000)).toBe('KSh 2.0M');
    expect(formatCompactCurrency(500)).toMatch(/500/);
    expect(formatCompactCurrency(null)).toMatch(/0\.00/);
  });

  it('formatCompactNumber handles invalid input', () => {
    expect(formatCompactNumber('bad')).toBe('0');
  });
});
