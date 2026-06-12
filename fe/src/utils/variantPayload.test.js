import {
  buildVariantDraftPatchPayload,
  buildVariantPatchPayload,
  buildVariantUpdatePayload,
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
});

describe('buildVariantDraftPatchPayload', () => {
  test('sets price and stock from create drafts', () => {
    expect(
      buildVariantDraftPatchPayload({ price: '55.00', stock_quantity: '4', is_active: true })
    ).toEqual({
      price: '55.00',
      selling_price: '55.00',
      stock_quantity: 4,
      is_active: true,
    });
  });
});
