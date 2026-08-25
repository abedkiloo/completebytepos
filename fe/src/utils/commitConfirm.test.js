import { buildCommitRows, formatSignedQty } from './commitConfirm';

describe('commitConfirm helpers', () => {
  test('buildCommitRows drops empty values and normalizes fields', () => {
    expect(
      buildCommitRows([
        { label: 'Qty', value: '+3', tone: 'success', emphasis: true },
        { label: 'Skip', value: '' },
        { label: 'Also skip', value: null },
        { label: null, value: 'x' },
        null,
        { label: 1, value: 2 },
      ])
    ).toEqual([
      { label: 'Qty', value: '+3', tone: 'success', emphasis: true },
      { label: '1', value: '2', tone: 'default', emphasis: false },
    ]);
  });

  test('buildCommitRows tolerates missing or non-array input', () => {
    expect(buildCommitRows()).toEqual([]);
    expect(buildCommitRows(null)).toEqual([]);
    expect(buildCommitRows(undefined)).toEqual([]);
    expect(buildCommitRows({ label: 'x', value: 'y' })).toEqual([]);
  });

  test('formatSignedQty adds a plus for positive amounts', () => {
    expect(formatSignedQty(4)).toBe('+4');
    expect(formatSignedQty(-2)).toBe('-2');
    expect(formatSignedQty(0)).toBe('0');
    expect(formatSignedQty('3')).toBe('+3');
    expect(formatSignedQty(null)).toBe('0');
    expect(formatSignedQty(undefined)).toBe('0');
    expect(formatSignedQty('abc')).toBe('0');
  });
});
