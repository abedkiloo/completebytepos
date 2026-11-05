import {
  isDuplicateScan,
  looksLikeScanCode,
  normalizeScanCode,
  pickExactScanProduct,
  productMatchesScanCode,
} from './posBarcodeScan';

describe('posBarcodeScan', () => {
  it('normalizes and matches sku/barcode only', () => {
    expect(normalizeScanCode('  ABC  ')).toBe('ABC');
    expect(
      productMatchesScanCode({ sku: 'ABC', barcode: '123' }, 'abc')
    ).toBe(true);
    expect(
      productMatchesScanCode({ sku: 'X', barcode: '', name: 'Soap' }, 'Soap')
    ).toBe(false);
  });

  it('picks a single exact hit and rejects ambiguous', () => {
    const a = { id: 1, sku: 'S1', barcode: '111' };
    const b = { id: 2, sku: 'S1', barcode: '111' };
    expect(pickExactScanProduct([a], '111').reason).toBe('exact');
    expect(pickExactScanProduct([a, b], '111').reason).toBe('ambiguous');
    expect(pickExactScanProduct([], '111').reason).toBe('none');
  });

  it('allows single search hit for scan-like codes (variant parent)', () => {
    const parent = { id: 9, sku: 'PARENT', barcode: '', name: 'Shirt' };
    expect(pickExactScanProduct([parent], '8901234567890').product).toBe(parent);
    expect(looksLikeScanCode('8901234567890')).toBe(true);
    expect(looksLikeScanCode('ab')).toBe(false);
  });

  it('debounces duplicate scans', () => {
    const last = { code: '111', at: Date.now() };
    expect(isDuplicateScan(last, '111', 450)).toBe(true);
    expect(isDuplicateScan({ code: '111', at: Date.now() - 800 }, '111')).toBe(
      false
    );
  });
});
