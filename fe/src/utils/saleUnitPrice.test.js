import {
  isSaleUnitPriceOverrideAllowed,
  saleUnitPriceOverrideError,
} from './saleUnitPrice';

describe('saleUnitPrice', () => {
  it('allows charging catalog price or higher', () => {
    expect(
      isSaleUnitPriceOverrideAllowed({
        catalogPrice: 20,
        requestedPrice: 20,
      })
    ).toBe(true);
    expect(
      isSaleUnitPriceOverrideAllowed({
        catalogPrice: 20,
        requestedPrice: 50,
      })
    ).toBe(true);
  });

  it('blocks undercutting catalog price for cashiers', () => {
    expect(
      isSaleUnitPriceOverrideAllowed({
        catalogPrice: 20,
        requestedPrice: 15,
        mayEditPricing: false,
      })
    ).toBe(false);
    expect(
      saleUnitPriceOverrideError({
        catalogPrice: 20,
        requestedPrice: 15,
        mayEditPricing: false,
      })
    ).toMatch(/below the selling price/i);
  });

  it('blocks undercutting catalog price even for pricing editors', () => {
    expect(
      isSaleUnitPriceOverrideAllowed({
        catalogPrice: 20,
        requestedPrice: 5,
        mayEditPricing: true,
      })
    ).toBe(false);
    expect(
      saleUnitPriceOverrideError({
        catalogPrice: 20,
        requestedPrice: 5,
        mayEditPricing: true,
      })
    ).toMatch(/below the selling price/i);
  });

  it('rejects negative prices', () => {
    expect(
      isSaleUnitPriceOverrideAllowed({
        catalogPrice: 20,
        requestedPrice: -1,
        mayEditPricing: true,
      })
    ).toBe(false);
  });
});
