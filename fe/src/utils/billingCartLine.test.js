import { resolveCartVariantId, buildBillingCartLine } from './billingCartLine';

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
  });

  it('buildBillingCartLine keeps product_id and correct variant_id for holding sync', () => {
    const line = buildBillingCartLine(product, {
      id: 5,
      variant_id: 12,
      variant: { id: 12, sku: 'WEB-L-B', stock_quantity: 0 },
      price: 500,
      stock_quantity: 50,
      quantity: 2,
    });
    expect(line.id).toBe(5);
    expect(line.variant_id).toBe(12);
    expect(line.price).toBe(500);
    expect(line.quantity).toBe(2);
    expect(line.stock_quantity).toBe(50);
  });
});
