import {
  buildDuplicateRefundQtyMap,
  detectDuplicateSaleLineGroups,
  duplicateExcessSaleItemIds,
  hasDuplicateSaleLines,
} from './detectDuplicateSaleLines';
import { saleItemRefundableQuantity } from './saleItemDisplay';

describe('detectDuplicateSaleLines', () => {
  const items = [
    { id: 1, product_id: 10, variant_id: 100, quantity: 2 },
    { id: 2, product_id: 10, variant_id: 100, quantity: 1 },
    { id: 3, product_id: 20, variant_id: null, quantity: 1 },
  ];

  it('groups duplicate product+variant lines', () => {
    const groups = detectDuplicateSaleLineGroups(items);
    expect(groups).toHaveLength(1);
    expect(groups[0].lines.map((l) => l.id)).toEqual([1, 2]);
  });

  it('detects duplicate presence', () => {
    expect(hasDuplicateSaleLines(items)).toBe(true);
    expect(hasDuplicateSaleLines([items[2]])).toBe(false);
  });

  it('marks excess duplicate line ids', () => {
    expect(duplicateExcessSaleItemIds(items)).toEqual([2]);
  });

  it('builds refund map for duplicate lines only', () => {
    const withRefundable = items.map((item) => ({
      ...item,
      refundable_quantity: item.quantity,
    }));
    expect(buildDuplicateRefundQtyMap(withRefundable)).toEqual({
      1: 0,
      2: saleItemRefundableQuantity(withRefundable[1]),
      3: 0,
    });
  });

  it('does not treat different variants as duplicates', () => {
    const mixed = [
      { id: 1, product_id: 10, variant_id: 100, quantity: 1 },
      { id: 2, product_id: 10, variant_id: 101, quantity: 1 },
    ];
    expect(hasDuplicateSaleLines(mixed)).toBe(false);
    expect(duplicateExcessSaleItemIds(mixed)).toEqual([]);
  });

  it('keeps first line per group when marking excess duplicates', () => {
    const three = [
      { id: 1, product_id: 5, variant_id: null, quantity: 1 },
      { id: 2, product_id: 5, variant_id: null, quantity: 2 },
      { id: 3, product_id: 5, variant_id: null, quantity: 1 },
    ];
    expect(duplicateExcessSaleItemIds(three)).toEqual([2, 3]);
    const map = buildDuplicateRefundQtyMap(
      three.map((item) => ({ ...item, refundable_quantity: item.quantity }))
    );
    expect(map[1]).toBe(0);
    expect(map[2]).toBe(2);
    expect(map[3]).toBe(1);
  });
});
