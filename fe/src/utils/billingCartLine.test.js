import { resolveCartVariantId, buildBillingCartLine, holdingSaleItemToCartLine } from './billingCartLine';

describe('billingCartLine', () => {
  const product = {
    id: 5,
    name: 'Webbing',
    sku: 'WEB-1',
    price: '100',
    stock_quantity: 50,
    has_variants: true,
    track_stock: true,
  };

  it('resolveCartVariantId uses variant_id from picker payload, not product id', () => {
    const payload = {
      id: 5,
      variant_id: 12,
      variant: { id: 12, sku: 'WEB-M-B' },
      price: 500,
    };
    expect(resolveCartVariantId(5, payload)).toBe(12);
    expect(resolveCartVariantId(5, { id: 5 })).toBeNull();
    expect(resolveCartVariantId(5, null)).toBeNull();
    expect(resolveCartVariantId(5, { variant: { id: 99 } })).toBe(99);
    expect(resolveCartVariantId(5, { id: 88 })).toBe(88);
  });

  it('buildBillingCartLine keeps product_id and correct variant_id for holding sync', () => {
    const line = buildBillingCartLine(product, {
      id: 5,
      variant_id: 12,
      variant: { id: 12, sku: 'WEB-L-B', size_name: 'Large', color_name: 'Blue', stock_quantity: 0 },
      price: 500,
      stock_quantity: 50,
      quantity: 2,
    });
    expect(line.id).toBe(5);
    expect(line.variant_id).toBe(12);
    expect(line.price).toBe(500);
    expect(line.quantity).toBe(2);
    expect(line.stock_quantity).toBe(50);
    expect(line.size_name).toBe('Large');
    expect(line.color_name).toBe('Blue');
    expect(line.variant).toEqual(
      expect.objectContaining({ id: 12, size_name: 'Large', color_name: 'Blue' })
    );
  });

  it('buildBillingCartLine without variant uses product pricing', () => {
    const line = buildBillingCartLine(product, null, { validateStock: false });
    expect(line.variant_id).toBeNull();
    expect(line.price).toBe(100);
    expect(line.validateStock).toBe(false);
    expect(line.mrp).toBe(100);
  });

  it('buildBillingCartLine reads effective_price from variant row when parent price empty', () => {
    const line = buildBillingCartLine(
      { id: 1, name: 'A' },
      { variant: { effective_price: '55', effective_mrp: '60', cost: '20' } }
    );
    expect(line.selling_price).toBe(55);
    expect(line.mrp).toBe(60);
    expect(line.cost).toBe(20);
  });

  it('holdingSaleItemToCartLine restores quantity from holding item', () => {
    const line = holdingSaleItemToCartLine(
      {
        product_id: 5,
        product_name: 'Webbing',
        quantity: 4,
        unit_price: '500',
        variant_id: 12,
        size_name: 'Large',
        color_name: 'White',
        product: { id: 5, name: 'Webbing', stock_quantity: 50, track_stock: true },
      },
      { validateStock: false }
    );
    expect(line.quantity).toBe(4);
    expect(line.price).toBe(500);
    expect(line.name).toBe('Webbing');
    expect(line.size_name).toBe('Large');
    expect(line.color_name).toBe('White');
    expect(line.variant_id).toBe(12);
  });

  it('caps quantity to stock when validateStock is enabled', () => {
    const line = holdingSaleItemToCartLine(
      {
        product_id: 5,
        product_name: 'Webbing',
        quantity: 10,
        unit_price: '500',
        product: { id: 5, name: 'Webbing', stock_quantity: 3, track_stock: true },
      },
      { validateStock: true }
    );
    expect(line.quantity).toBe(3);
  });
});
