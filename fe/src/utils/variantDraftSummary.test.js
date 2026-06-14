import {
  buildVariantDraftSummary,
  combinationKeyLabel,
  hasVariantDraftContent,
} from './variantDraftSummary';

describe('variantDraftSummary', () => {
  const sizes = [
    { id: 1, name: 'Large' },
    { id: 2, name: 'Medium' },
  ];
  const colors = [
    { id: 10, name: 'White' },
    { id: 11, name: 'Blue' },
  ];

  test('combinationKeyLabel renders color and size names', () => {
    expect(combinationKeyLabel('1-10', sizes, colors)).toBe('White / Large');
    expect(combinationKeyLabel('2-11', sizes, colors)).toBe('Blue / Medium');
  });

  test('hasVariantDraftContent detects stock or price', () => {
    expect(hasVariantDraftContent({ stock_quantity: '' })).toBe(false);
    expect(hasVariantDraftContent({ stock_quantity: '45' })).toBe(true);
    expect(hasVariantDraftContent({ stock_quantity: 0 })).toBe(true);
    expect(hasVariantDraftContent({ price: '100' })).toBe(true);
    expect(hasVariantDraftContent({ mrp: '120' })).toBe(true);
    expect(hasVariantDraftContent({ cost: '40' })).toBe(true);
  });

  test('combinationKeyLabel falls back to default variant', () => {
    expect(combinationKeyLabel('none-none', [], [])).toBe('Default variant');
  });

  test('buildVariantDraftSummary keeps all configured combinations', () => {
    const summary = buildVariantDraftSummary(
      {
        '1-10': { stock_quantity: '45', price: '' },
        '2-10': { stock_quantity: '20', price: '500' },
        '2-11': { stock_quantity: '', price: '' },
      },
      { sizes, colors }
    );

    expect(summary.count).toBe(2);
    expect(summary.totalStock).toBe(65);
    expect(summary.lines[0].label).toBe('White / Large');
    expect(summary.lines[0].details).toContain('stock 45');
    expect(summary.lines[1].label).toBe('White / Medium');
    expect(summary.lines[1].details).toEqual(['price KES 500', 'stock 20']);
  });

  test('buildVariantDraftSummary includes mrp and cost details', () => {
    const summary = buildVariantDraftSummary(
      {
        '1-10': { mrp: '150', cost: '60', price: '120' },
      },
      { sizes, colors }
    );
    expect(summary.count).toBe(1);
    expect(summary.lines[0].details).toContain('MRP KES 150');
    expect(summary.lines[0].details).toContain('cost KES 60');
    expect(summary.lines[0].details).toContain('price KES 120');
  });

  test('buildVariantDraftSummary handles empty drafts', () => {
    expect(buildVariantDraftSummary({}, { sizes, colors })).toEqual({
      lines: [],
      totalStock: 0,
      count: 0,
    });
  });
});
