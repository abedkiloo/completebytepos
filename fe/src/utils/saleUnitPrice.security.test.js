import {
  isSaleUnitPriceOverrideAllowed,
  lineCatalogFloor,
  saleUnitPriceOverrideError,
} from './saleUnitPrice';

/**
 * Security: unit-price floor cannot be bypassed via mayEditPricing or by
 * treating charged markup as the catalog floor when catalog_price is present.
 */
describe('saleUnitPrice security', () => {
  it('never allows undercutting catalog even when mayEditPricing is true', () => {
    expect(
      isSaleUnitPriceOverrideAllowed({
        catalogPrice: 1800,
        requestedPrice: 1799.99,
        mayEditPricing: true,
      })
    ).toBe(false);
    expect(
      saleUnitPriceOverrideError({
        catalogPrice: 1800,
        requestedPrice: 1,
        mayEditPricing: true,
      })
    ).toBeTruthy();
  });

  it('does not treat charged markup as floor when catalog_price is stamped', () => {
    const floor = lineCatalogFloor({
      catalog_price: 1800,
      selling_price: 17600,
      price: 17600,
    });
    expect(floor).toBe(1800);
    expect(
      isSaleUnitPriceOverrideAllowed({
        catalogPrice: floor,
        requestedPrice: 1800,
        mayEditPricing: false,
      })
    ).toBe(true);
  });

  it('rejects non-numeric and negative overrides (no privilege escalation via NaN)', () => {
    expect(
      isSaleUnitPriceOverrideAllowed({
        catalogPrice: 10,
        requestedPrice: 'abc',
        mayEditPricing: true,
      })
    ).toBe(false);
    expect(
      isSaleUnitPriceOverrideAllowed({
        catalogPrice: 10,
        requestedPrice: -0.01,
        mayEditPricing: true,
      })
    ).toBe(false);
  });
});
