import {
  displayStatus,
  fieldLoadHasSales,
  fieldLoadNoSalesLabel,
  fieldLoadSaleCount,
  loadBuckets,
  loadMatchesFilter,
  missingUnits,
  saleBasketTotal,
  saleTotal,
  statusLabel,
} from './fieldLoad';

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
    expect(saleBasketTotal([
      { unitPrice: '50', quantity: 2 },
      { unitPrice: '50', quantity: 0 },
      { unitPrice: '30', quantity: 1 },
    ])).toBe(130);
    expect(saleBasketTotal(null)).toBe(0);
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

  test('each tab keeps only its own loads, including 300 mixed rows', () => {
    const waiting = { status: 'awaiting_issue', lines: [] };
    const open = { status: 'open', lines: [] };
    const shortage = { status: 'pending_review', lines: [{ quantity_missing: 2 }] };
    expect(loadMatchesFilter(waiting, 'awaiting')).toBe(true);
    expect(loadMatchesFilter(waiting, 'open')).toBe(false);
    expect(loadMatchesFilter(open, 'awaiting')).toBe(false);
    expect(loadMatchesFilter(shortage, 'shortage')).toBe(true);
    expect(loadMatchesFilter(shortage, 'awaiting')).toBe(false);
    expect(loadMatchesFilter(null, 'all')).toBe(false);
    const mixed = Array.from({ length: 300 }, (_, index) => (
      index % 2 === 0 ? waiting : open
    ));
    expect(mixed.filter((row) => loadMatchesFilter(row, 'awaiting'))).toHaveLength(150);
    expect(mixed.filter((row) => loadMatchesFilter(row, 'open'))).toHaveLength(150);
  });

  test('unit: a load with no sales is labeled clearly', () => {
    expect(fieldLoadHasSales({ sales: [], units_sold: 0, lines: [] })).toBe(false);
    expect(fieldLoadNoSalesLabel({ status: 'open', sales: [] })).toBe('No sales yet on this load.');
    expect(fieldLoadNoSalesLabel({ status: 'accepted', sales: [] })).toBe('No sales on this load.');
    expect(fieldLoadSaleCount({ sales: [] })).toBe(0);
  });

  test('corrected: sales on the load clear the empty label', () => {
    const withSales = {
      status: 'open',
      sales: [{ id: 1, sale_number: 'S-1', total: '100.00' }],
      units_sold: 2,
    };
    expect(fieldLoadHasSales(withSales)).toBe(true);
    expect(fieldLoadNoSalesLabel(withSales)).toBe('');
    expect(fieldLoadSaleCount(withSales)).toBe(1);
    expect(fieldLoadHasSales({ sales: [], units_sold: 0, lines: [{ quantity_sold: 3 }] })).toBe(true);
  });

  test('stress: empty-sale detection stays correct across many loads', () => {
    for (let i = 0; i < 400; i += 1) {
      const empty = { sales: [], units_sold: 0, lines: [{ quantity_sold: 0 }] };
      const filled = { sales: [{ id: i }], units_sold: i + 1 };
      expect(fieldLoadHasSales(empty)).toBe(false);
      expect(fieldLoadHasSales(filled)).toBe(true);
    }
  });

  test('security: no-sale helpers never echo a phone number', () => {
    const label = fieldLoadNoSalesLabel({
      status: 'open',
      sales: [],
      agent_phone: '0718000999',
    });
    expect(label).toBe('No sales yet on this load.');
    expect(label).not.toMatch(/07\d/);
    expect(fieldLoadHasSales(null)).toBe(false);
  });
});
