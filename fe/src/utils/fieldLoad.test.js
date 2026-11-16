import { displayStatus, loadBuckets, missingUnits, saleTotal, statusLabel } from './fieldLoad';

describe('field load math', () => {
  test('missing is taken minus sold minus returned, and blank means not counted', () => {
    expect(missingUnits(40, 5, 35)).toBe(0);
    expect(missingUnits(20, 10, 8)).toBe(2);
    expect(missingUnits(15, 0, '')).toBeNull();
    expect(missingUnits(15, 0, null)).toBeNull();
  });

  test('a pending load with a gap is a shortage, and a field order status is not invented', () => {
    expect(displayStatus({
      status: 'pending_review',
      lines: [{ quantity_missing: 2 }],
    })).toBe('shortage');
    expect(displayStatus({ status: 'open', display_status: 'open', lines: [] })).toBe('open');
    expect(statusLabel('shortage')).toBe('Shortage');
    expect(saleTotal('150', 5)).toBe(750);
    expect(saleTotal('nope', 1)).toBe(0);
  });

  test('tiles count each display status once across 300 loads', () => {
    const loads = Array.from({ length: 300 }, (_, index) => ({
      status: index % 4 === 0 ? 'open' : 'accepted',
      lines: [],
    }));
    const buckets = loadBuckets(loads);
    expect(buckets.active + buckets.accepted).toBe(300);
    expect(buckets.shortage).toBe(0);
  });
});
