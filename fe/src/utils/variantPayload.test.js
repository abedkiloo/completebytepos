import {
  buildVariantDraftPatchPayload,
  buildVariantPatchPayload,
  buildVariantUpdatePayload,
  variantFinancialValidationMessage,
} from './variantPayload';

describe('buildVariantUpdatePayload', () => {
  const variant = {
    id: 3,
    product: 8,
    size: 1,
    color: 2,
    sku: 'WATER-500-S',
    barcode: null,
    mrp: '120.00',
    cost: '40.00',
    low_stock_threshold: 5,
    price: '100.00',
  };

  test('includes identity fields required by the API', () => {
    const payload = buildVariantUpdatePayload(variant, {
      price: '110.00',
      stock_quantity: '12',
      is_active: true,
    });

    expect(payload).toMatchObject({
      product: 8,
      size: 1,
      color: 2,
      sku: 'WATER-500-S',
      price: '110.00',
      selling_price: '110.00',
      stock_quantity: 12,
      is_active: true,
      mrp: '120.00',
      cost: '40.00',
      low_stock_threshold: 5,
    });
  });

  test('maps empty price to null', () => {
    const payload = buildVariantUpdatePayload(variant, {
      price: '',
      stock_quantity: 0,
      is_active: false,
    });
    expect(payload.price).toBeNull();
    expect(payload.selling_price).toBeNull();
    expect(payload.is_active).toBe(false);
  });

  test('draft overrides mrp and cost', () => {
    const payload = buildVariantUpdatePayload(variant, {
      mrp: '140.00',
      cost: '45.00',
      price: '110.00',
      stock_quantity: '3',
      is_active: true,
    });
    expect(payload.mrp).toBe('140.00');
    expect(payload.cost).toBe('45.00');
  });
});

describe('buildVariantPatchPayload', () => {
  const variant = {
    id: 3,
    product: 8,
    price: '100.00',
    stock_quantity: 10,
    is_active: true,
  };

  test('includes only changed fields', () => {
    expect(
      buildVariantPatchPayload(variant, { price: '100.00', stock_quantity: '15' })
    ).toEqual({ stock_quantity: 15 });
    expect(
      buildVariantPatchPayload({ ...variant, mrp: '150.00' }, { mrp: '160.00' })
    ).toEqual({ mrp: '160.00' });
  });

  test('returns empty object when nothing changed', () => {
    expect(
      buildVariantPatchPayload(variant, {
        price: '100.00',
        stock_quantity: '10',
        is_active: true,
      })
    ).toEqual({});
  });

  test('includes cost and is_active when changed', () => {
    expect(
      buildVariantPatchPayload({ ...variant, cost: '40.00' }, { cost: '50.00' })
    ).toEqual({ cost: '50.00' });
    expect(
      buildVariantPatchPayload(variant, { is_active: false })
    ).toEqual({ is_active: false });
  });

  test('ignores empty stock in patch', () => {
    expect(buildVariantPatchPayload(variant, { stock_quantity: '' })).toEqual({});
  });
});

describe('buildVariantDraftPatchPayload', () => {
  test('sets price, mrp, and stock from create drafts', () => {
    expect(
      buildVariantDraftPatchPayload({
        price: '55.00',
        mrp: '70.00',
        stock_quantity: '4',
        is_active: true,
      })
    ).toEqual({
      price: '55.00',
      selling_price: '55.00',
      mrp: '70.00',
      stock_quantity: 4,
      is_active: true,
    });
  });

  test('includes cost and omits empty mrp', () => {
    expect(buildVariantDraftPatchPayload({ cost: '12.00', mrp: '' })).toEqual({
      cost: '12.00',
    });
    expect(buildVariantDraftPatchPayload({ is_active: false })).toEqual({
      is_active: false,
    });
  });
});

describe('variantFinancialValidationMessage', () => {
  test('flags price below cost with variant label', () => {
    expect(
      variantFinancialValidationMessage(
        { price: '40', cost: '50' },
        { label: 'Large / Blue' }
      )
    ).toBe(
      'Selling price should be greater than or equal to cost price for variant Large / Blue.'
    );
  });

  test('flags MRP below price with variant label', () => {
    expect(
      variantFinancialValidationMessage(
        { price: '100', mrp: '80' },
        { label: 'Medium / Red', canEditMrp: true }
      )
    ).toBe('MRP should be at least the selling price for variant Medium / Red.');
  });

  test('returns null when valid', () => {
    expect(
      variantFinancialValidationMessage(
        { price: '100', cost: '50', mrp: '120' },
        { label: 'Large / Blue', canEditMrp: true }
      )
    ).toBeNull();
  });
});
