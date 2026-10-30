import { correctionLooksUnchanged } from './correctionUnchanged';

describe('correctionLooksUnchanged', () => {
  const snapshot = {
    total: 2500,
    paid: 2500,
    itemCount: 1,
    paymentMethod: 'cash',
  };

  test('returns false without a snapshot', () => {
    expect(correctionLooksUnchanged(null, { total: 2500, paid: 2500 })).toBe(false);
  });

  test('detects matching Was → Now totals', () => {
    expect(
      correctionLooksUnchanged(snapshot, {
        total: 2500,
        paid: 2500,
        itemCount: 1,
        paymentMethod: 'cash',
      })
    ).toBe(true);
  });

  test('detects total, paid, item, or method changes', () => {
    expect(
      correctionLooksUnchanged(snapshot, {
        total: 2400,
        paid: 2500,
        itemCount: 1,
        paymentMethod: 'cash',
      })
    ).toBe(false);
    expect(
      correctionLooksUnchanged(snapshot, {
        total: 2500,
        paid: 2000,
        itemCount: 1,
        paymentMethod: 'cash',
      })
    ).toBe(false);
    expect(
      correctionLooksUnchanged(snapshot, {
        total: 2500,
        paid: 2500,
        itemCount: 2,
        paymentMethod: 'cash',
      })
    ).toBe(false);
    expect(
      correctionLooksUnchanged(snapshot, {
        total: 2500,
        paid: 2500,
        itemCount: 1,
        paymentMethod: 'mpesa',
      })
    ).toBe(false);
  });
});
