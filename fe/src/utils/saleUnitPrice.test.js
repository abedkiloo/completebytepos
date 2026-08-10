import {
  isSaleUnitPriceOverrideAllowed,
  saleUnitPriceOverrideError,
} from './saleUnitPrice';

describe('saleUnitPrice', () => {
  it('allows sales staff to charge catalog price or higher', () => {
    expect(
      isSaleUnitPriceOverrideAllowed({
        catalogPrice: 20,
        requestedPrice: 20,
        mayEditPricing: false,
      })
    ).toBe(true);
    expect(
      isSaleUnitPriceOverrideAllowed({
        catalogPrice: 20,
        requestedPrice: 50,
        mayEditPricing: false,
      })
    ).toBe(true);
  });

  it('blocks sales staff from undercutting catalog price', () => {
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

  it('allows managers to set any non-negative price', () => {
    expect(
      isSaleUnitPriceOverrideAllowed({
        catalogPrice: 20,
        requestedPrice: 5,
        mayEditPricing: true,
      })
    ).toBe(true);
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
