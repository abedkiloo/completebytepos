import { buildVariantCartPayload } from '../../utils/variantSelector';

/**
 * Regression: double Add with qty N must not become 2N when the cart merges by sum.
 * Mirrors VariantSelector submittedRef + usePOSState picker debounce.
 */
describe('variant add single-flight (qty doubling guard)', () => {
  function mergeCart(prev, product) {
    const key = `${product.id}:${product.variant_id || ''}`;
    const qtyToAdd = product.quantity || 1;
    const existing = prev.find((item) => `${item.id}:${item.variant_id || ''}` === key);
    if (existing) {
      return prev.map((item) =>
        `${item.id}:${item.variant_id || ''}` === key
          ? { ...item, quantity: item.quantity + qtyToAdd }
          : item
      );
    }
    return [...prev, { ...product, quantity: qtyToAdd }];
  }

  function guardedAdd(cart, product, lastRef) {
    const key = `${product.id}:${product.variant_id || ''}`;
    const qtyToAdd = product.quantity || 1;
    if (product.quantity != null) {
      const stamp = `${key}:${qtyToAdd}`;
      const now = Date.now();
      if (lastRef.stamp === stamp && now - lastRef.at < 500) {
        return cart;
      }
      lastRef.stamp = stamp;
      lastRef.at = now;
    }
    return mergeCart(cart, product);
  }

  it('keeps qty 3 when Add fires twice with quantity 3', () => {
    const product = buildVariantCartPayload(
      { id: 9, name: 'Sofa', price: 100, has_variants: false },
      null,
      3
    );
    const lastRef = { stamp: '', at: 0 };
    let cart = [];
    cart = guardedAdd(cart, product, lastRef);
    cart = guardedAdd(cart, product, lastRef);
    expect(cart).toHaveLength(1);
    expect(cart[0].quantity).toBe(3);
  });

  it('keeps qty 1 when Add fires twice with quantity 1', () => {
    const product = buildVariantCartPayload(
      { id: 2, name: 'Chair', price: 50, has_variants: false },
      null,
      1
    );
    const lastRef = { stamp: '', at: 0 };
    let cart = [];
    cart = guardedAdd(cart, product, lastRef);
    cart = guardedAdd(cart, product, lastRef);
    expect(cart[0].quantity).toBe(1);
  });
});
