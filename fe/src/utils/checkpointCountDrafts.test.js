import {
  buildChangedCountPayload,
  hasAnyChangedPendingDraft,
  isCountDraftChanged,
  parseCountDraft,
  sortCheckpointLines,
  systemQtyAtOpen,
} from './checkpointCountDrafts';

describe('parseCountDraft', () => {
  it('parses non-negative integers', () => {
    expect(parseCountDraft('0')).toBe(0);
    expect(parseCountDraft('12')).toBe(12);
    expect(parseCountDraft(' 7 ')).toBe(7);
  });

  it('rejects empty, negative, and non-numeric', () => {
    expect(parseCountDraft('')).toBeNull();
    expect(parseCountDraft('   ')).toBeNull();
    expect(parseCountDraft(null)).toBeNull();
    expect(parseCountDraft(undefined)).toBeNull();
    expect(parseCountDraft('-1')).toBeNull();
    expect(parseCountDraft('abc')).toBeNull();
  });
});

describe('systemQtyAtOpen', () => {
  it('reads snapshot qty', () => {
    expect(systemQtyAtOpen({ system_qty_at_open: 10 })).toBe(10);
    expect(systemQtyAtOpen({})).toBe(0);
    expect(systemQtyAtOpen(null)).toBe(0);
  });
});

describe('isCountDraftChanged', () => {
  const line = { id: 1, system_qty_at_open: 10, product_name: 'Widget' };

  it('is false when draft matches system qty (save disabled for now)', () => {
    expect(isCountDraftChanged(line, '10')).toBe(false);
    expect(isCountDraftChanged(line, 10)).toBe(false);
  });

  it('is true when draft differs', () => {
    expect(isCountDraftChanged(line, '9')).toBe(true);
    expect(isCountDraftChanged(line, '11')).toBe(true);
    expect(isCountDraftChanged(line, '0')).toBe(true);
  });

  it('is false for invalid drafts', () => {
    expect(isCountDraftChanged(line, '')).toBe(false);
    expect(isCountDraftChanged(line, '-3')).toBe(false);
    expect(isCountDraftChanged(line, 'x')).toBe(false);
  });
});

describe('sortCheckpointLines', () => {
  it('puts pending before counted', () => {
    const lines = [
      { id: 2, status: 'counted', counted_at: '2026-10-19T10:00:00Z' },
      { id: 1, status: 'pending' },
      { id: 3, status: 'counted', counted_at: '2026-10-19T09:00:00Z' },
    ];
    expect(sortCheckpointLines(lines).map((l) => l.id)).toEqual([1, 3, 2]);
  });

  it('handles empty', () => {
    expect(sortCheckpointLines(null)).toEqual([]);
    expect(sortCheckpointLines([])).toEqual([]);
  });
});

describe('buildChangedCountPayload / hasAnyChangedPendingDraft', () => {
  const pending = [
    { id: 1, system_qty_at_open: 5, product_name: 'A', status: 'pending' },
    { id: 2, system_qty_at_open: 8, product_name: 'B', status: 'pending' },
  ];

  it('reports no changes when drafts match system', () => {
    const drafts = { 1: '5', 2: '8' };
    expect(hasAnyChangedPendingDraft(pending, drafts)).toBe(false);
    expect(buildChangedCountPayload(pending, drafts)).toEqual({ payload: [] });
  });

  it('includes only changed lines', () => {
    const drafts = { 1: '5', 2: '3' };
    expect(hasAnyChangedPendingDraft(pending, drafts)).toBe(true);
    expect(buildChangedCountPayload(pending, drafts)).toEqual({
      payload: [{ line_id: 2, counted_qty: 3 }],
    });
  });

  it('includes all when all changed', () => {
    const drafts = { 1: '4', 2: '9' };
    expect(buildChangedCountPayload(pending, drafts).payload).toEqual([
      { line_id: 1, counted_qty: 4 },
      { line_id: 2, counted_qty: 9 },
    ]);
  });

  it('handles empty pending / missing drafts', () => {
    expect(hasAnyChangedPendingDraft([], {})).toBe(false);
    expect(hasAnyChangedPendingDraft(null, null)).toBe(false);
    expect(buildChangedCountPayload(null, null)).toEqual({ payload: [] });
    expect(buildChangedCountPayload(pending, {})).toEqual({ payload: [] });
  });
});

describe('sortCheckpointLines ties', () => {
  it('falls back to id when counted_at ties', () => {
    const lines = [
      { id: 5, status: 'counted', counted_at: '2026-10-19T10:00:00Z' },
      { id: 2, status: 'counted', counted_at: '2026-10-19T10:00:00Z' },
    ];
    expect(sortCheckpointLines(lines).map((l) => l.id)).toEqual([2, 5]);
  });

  it('treats missing counted_at as epoch for counted rows', () => {
    const lines = [
      { id: 2, status: 'counted', counted_at: '2026-10-19T10:00:00Z' },
      { id: 1, status: 'counted' },
    ];
    expect(sortCheckpointLines(lines).map((l) => l.id)).toEqual([1, 2]);
  });

  it('sorts pending by id', () => {
    const lines = [
      { id: 9, status: 'pending' },
      { id: 3, status: 'pending' },
    ];
    expect(sortCheckpointLines(lines).map((l) => l.id)).toEqual([3, 9]);
  });

  it('falls back to 0 when id is missing', () => {
    const lines = [{ status: 'pending', product_name: 'A' }, { id: 1, status: 'pending' }];
    expect(sortCheckpointLines(lines)[0].id).toBeUndefined();
    expect(sortCheckpointLines(lines)[1].id).toBe(1);
  });

  it('treats invalid counted_at as 0', () => {
    const lines = [
      { id: 2, status: 'counted', counted_at: 'not-a-date' },
      { id: 1, status: 'counted', counted_at: '2026-10-19T10:00:00Z' },
    ];
    expect(sortCheckpointLines(lines).map((l) => l.id)).toEqual([2, 1]);
  });
});
