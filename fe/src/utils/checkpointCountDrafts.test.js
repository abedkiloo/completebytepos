import {
  buildChangedCountPayload,
  buildCloseCheckpointSummary,
  buildPendingCountPayload,
  hasAnyChangedPendingDraft,
  hasAnySavablePendingDraft,
  isCountDraftChanged,
  isCountDraftSavable,
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

describe('isCountDraftChanged / isCountDraftSavable', () => {
  const line = { id: 1, system_qty_at_open: 10, product_name: 'Widget', status: 'pending' };

  it('marks unchanged pending drafts as savable (confirm) but not changed', () => {
    expect(isCountDraftChanged(line, '10')).toBe(false);
    expect(isCountDraftSavable(line, '10')).toBe(true);
  });

  it('is true when draft differs', () => {
    expect(isCountDraftChanged(line, '9')).toBe(true);
    expect(isCountDraftSavable(line, '9')).toBe(true);
  });

  it('is false for invalid drafts', () => {
    expect(isCountDraftChanged(line, '')).toBe(false);
    expect(isCountDraftSavable(line, '')).toBe(false);
    expect(isCountDraftSavable(line, '-3')).toBe(false);
  });

  it('for counted lines only allows a real correction', () => {
    const counted = {
      id: 2,
      status: 'counted',
      system_qty_at_open: 10,
      counted_qty: 5048,
    };
    expect(isCountDraftChanged(counted, '5048')).toBe(false);
    expect(isCountDraftSavable(counted, '5048')).toBe(false);
    expect(isCountDraftChanged(counted, '548')).toBe(true);
    expect(isCountDraftSavable(counted, '548')).toBe(true);
    expect(
      isCountDraftChanged({ status: 'counted', counted_qty: null }, '0')
    ).toBe(false);
    expect(
      isCountDraftChanged({ status: 'counted', counted_qty: null }, '2')
    ).toBe(true);
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

describe('buildPendingCountPayload / hasAnySavablePendingDraft', () => {
  const pending = [
    { id: 1, system_qty_at_open: 5, product_name: 'A', status: 'pending' },
    { id: 2, system_qty_at_open: 8, product_name: 'B', status: 'pending' },
  ];

  it('includes unchanged lines as confirmable', () => {
    const drafts = { 1: '5', 2: '8' };
    expect(hasAnyChangedPendingDraft(pending, drafts)).toBe(false);
    expect(hasAnySavablePendingDraft(pending, drafts)).toBe(true);
    expect(buildPendingCountPayload(pending, drafts)).toEqual({
      payload: [
        { line_id: 1, counted_qty: 5 },
        { line_id: 2, counted_qty: 8 },
      ],
    });
    expect(buildChangedCountPayload(pending, drafts)).toEqual({ payload: [] });
  });

  it('includes changed and unchanged together', () => {
    const drafts = { 1: '5', 2: '3' };
    expect(buildPendingCountPayload(pending, drafts).payload).toEqual([
      { line_id: 1, counted_qty: 5 },
      { line_id: 2, counted_qty: 3 },
    ]);
    expect(buildChangedCountPayload(pending, drafts)).toEqual({
      payload: [{ line_id: 2, counted_qty: 3 }],
    });
  });

  it('handles empty pending / missing drafts', () => {
    expect(hasAnySavablePendingDraft([], {})).toBe(false);
    expect(hasAnySavablePendingDraft(null, null)).toBe(false);
    expect(hasAnyChangedPendingDraft(null, null)).toBe(false);
    expect(buildPendingCountPayload(null, null)).toEqual({ payload: [] });
    expect(buildPendingCountPayload(pending, {})).toEqual({ payload: [] });
    expect(buildChangedCountPayload([], { 1: '9' })).toEqual({ payload: [] });
    expect(isCountDraftChanged(null, '')).toBe(false);
    expect(isCountDraftChanged(null, '1')).toBe(true);
    expect(isCountDraftSavable(null, '1')).toBe(true);
  });
});

describe('buildCloseCheckpointSummary', () => {
  it('summarises unchanged vs adjusted lines', () => {
    const summary = buildCloseCheckpointSummary([
      {
        id: 1,
        status: 'counted',
        product_name: 'A',
        system_qty_at_open: 10,
        counted_qty: 10,
      },
      {
        id: 2,
        status: 'counted',
        product_name: 'B',
        system_qty_at_open: 5,
        counted_qty: 8,
      },
      {
        id: 3,
        status: 'counted',
        product_name: 'C',
        system_qty_at_open: 20,
        counted_qty: 12,
      },
      { id: 4, status: 'pending', system_qty_at_open: 1 },
    ]);
    expect(summary.counted).toBe(3);
    expect(summary.pending).toBe(1);
    expect(summary.unchanged).toBe(1);
    expect(summary.adjustedUp).toBe(1);
    expect(summary.adjustedDown).toBe(1);
    expect(summary.unitsUp).toBe(3);
    expect(summary.unitsDown).toBe(8);
    expect(summary.netUnits).toBe(-5);
    expect(summary.adjustments[0].name).toBe('C');
  });

  it('notes all unchanged', () => {
    const summary = buildCloseCheckpointSummary([
      { id: 1, status: 'counted', system_qty_at_open: 4, counted_qty: 4 },
    ]);
    expect(summary.unchanged).toBe(1);
    expect(summary.adjustments).toEqual([]);
  });

  it('falls back labels and handles null lines', () => {
    expect(buildCloseCheckpointSummary(null)).toEqual(
      expect.objectContaining({
        totalLines: 0,
        counted: 0,
        pending: 0,
        adjustments: [],
      })
    );
    const summary = buildCloseCheckpointSummary([
      {
        id: 9,
        status: 'counted',
        system_qty_at_open: 1,
        counted_qty: 3,
      },
    ]);
    expect(summary.adjustments[0]).toEqual(
      expect.objectContaining({
        name: 'Product',
        sku: '',
        variant: '',
        delta: 2,
      })
    );
  });

  it('uses counted_qty fallback when missing on counted row', () => {
    const summary = buildCloseCheckpointSummary([
      { id: 1, status: 'counted', system_qty_at_open: 7 },
    ]);
    expect(summary.unchanged).toBe(1);
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
