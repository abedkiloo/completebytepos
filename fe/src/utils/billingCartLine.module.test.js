import { holdingSaleItemToCartLine } from './billingCartLine';

/**
 * Module: product_variants off → variant_id cleared; catalog still resolves from product.
 */
describe('billingCartLine module gates', () => {
  afterEach(() => {
    localStorage.clear();
  });

  it('clears variant_id when product_variants feature is disabled', () => {
    localStorage.setItem(
      'enabled_modules',
      JSON.stringify({
        products: {
          is_enabled: true,
          features: { product_variants: { is_enabled: false } },
        },
      })
    );
    const line = holdingSaleItemToCartLine(
      {
        product_id: 5,
        product_name: 'Webbing',
        quantity: 1,
        unit_price: '900',
        variant_id: 12,
        variant: { id: 12, effective_price: '500' },
        product: {
          id: 5,
          name: 'Webbing',
          price: '400',
          selling_price: '400',
          stock_quantity: 10,
        },
      },
      { validateStock: false }
    );
    expect(line.variant_id).toBeNull();
    expect(line.catalog_price).toBe(400);
    expect(line.price).toBe(900);
  });

  it('keeps variant_id when product_variants feature is enabled', () => {
    localStorage.setItem(
      'enabled_modules',
      JSON.stringify({
        products: {
          is_enabled: true,
          features: { product_variants: { is_enabled: true } },
        },
      })
    );
    const line = holdingSaleItemToCartLine(
      {
        product_id: 5,
        product_name: 'Webbing',
        quantity: 1,
        unit_price: '900',
        variant_id: 12,
        variant: { id: 12, effective_price: '500' },
        product: {
          id: 5,
          name: 'Webbing',
          price: '400',
          selling_price: '400',
          stock_quantity: 10,
        },
      },
      { validateStock: false }
    );
    expect(line.variant_id).toBe(12);
    // Variant effective selling wins when a variant row is present.
    expect(line.catalog_price).toBe(500);
  });
});
