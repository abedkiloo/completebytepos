import {
  findVariantForSelection,
  getSellableStockForVariant,
  canAddVariantToCart,
  isVariantAddToCartDisabled,
  buildVariantCartPayload,
  variantMatchesSize,
} from './variantSelector';

const product = {
  id: 1,
  name: 'Webbing',
  price: '100',
  sku: 'WEB-1',
  has_variants: true,
  track_stock: true,
  stock_quantity: 50,
  unit: 'piece',
};

const variants = [
  {
    id: 10,
    size: 2,
    color: 5,
    size_name: 'Large',
    color_name: 'Blue',
    price: '1700',
    stock_quantity: 0,
    sku: 'WEB-L-B',
  },
  {
    id: 11,
    size: 3,
    color: 5,
    size_name: 'Medium',
    color_name: 'Blue',
    price: '1600',
    stock_quantity: 5,
    sku: 'WEB-M-B',
  },
];

const sizes = [
  { id: 2, name: 'Large', code: 'L' },
  { id: 3, name: 'Medium', code: 'M' },
];
const colors = [{ id: 5, name: 'Blue', hex_code: '#00f' }];

describe('variantSelector utils', () => {
  it('matches variant size id as number or nested object', () => {
    expect(variantMatchesSize({ size: { id: 2 } }, 2)).toBe(true);
    expect(variantMatchesSize({ size_id: '2' }, 2)).toBe(true);
  });

  it('findVariantForSelection resolves size + color', () => {
    const found = findVariantForSelection(variants, 2, 5, sizes, colors);
    expect(found?.id).toBe(10);
  });

  it('uses variant row stock only (not stale parent quantity)', () => {
    const staleParent = {
      ...product,
      stock_quantity: 50,
      variants: variants.map((v) => ({ ...v, stock_quantity: 0 })),
    };
    const variant = findVariantForSelection(
      staleParent.variants,
      2,
      5,
      sizes,
      colors
    );
    expect(
      getSellableStockForVariant(staleParent, variant, staleParent.variants)
    ).toBe(0);
  });

  it('does not use parent stock for a variant row when other variants hold stock', () => {
    const variant = findVariantForSelection(variants, 2, 5, sizes, colors);
    expect(getSellableStockForVariant(product, variant, variants)).toBe(0);
    expect(
      isVariantAddToCartDisabled({
        product,
        selectedVariant: variant,
        canAdd: true,
        validateStock: true,
        variantsList: variants,
      })
    ).toBe(true);
  });

  it('allows add when the selected variant row has stock', () => {
    const variant = findVariantForSelection(variants, 3, 5, sizes, colors);
    const canAdd = canAddVariantToCart({
      product,
      variants,
      selectedSize: 3,
      selectedColor: 5,
      selectedVariant: variant,
      availableSizes: sizes,
      availableColors: colors,
    });
    expect(canAdd).toBe(true);
    expect(
      isVariantAddToCartDisabled({
        product,
        selectedVariant: variant,
        canAdd,
        validateStock: true,
      })
    ).toBe(false);
  });

  it('blocks add when validateStock is true and both parent and variant stock are zero', () => {
    const empty = { ...product, stock_quantity: 0 };
    const variant = { ...variants[0], stock_quantity: 0 };
    expect(getSellableStockForVariant(empty, variant)).toBe(0);
    expect(
      isVariantAddToCartDisabled({
        product: empty,
        selectedVariant: variant,
        canAdd: true,
        validateStock: true,
      })
    ).toBe(true);
  });

  it('allows add at zero stock when validateStock is false', () => {
    const variant = findVariantForSelection(variants, 2, 5, sizes, colors);
    expect(
      isVariantAddToCartDisabled({
        product,
        selectedVariant: variant,
        canAdd: true,
        validateStock: false,
      })
    ).toBe(false);
  });

  it('allows add when product does not track stock', () => {
    const variant = findVariantForSelection(variants, 2, 5, sizes, colors);
    const noTrack = { ...product, track_stock: false };
    expect(getSellableStockForVariant(noTrack, variant)).toBe(null);
    expect(
      isVariantAddToCartDisabled({
        product: noTrack,
        selectedVariant: variant,
        canAdd: true,
        validateStock: true,
      })
    ).toBe(false);
  });

  it('buildVariantCartPayload includes effective stock on the line', () => {
    const variant = findVariantForSelection(variants, 3, 5, sizes, colors);
    const line = buildVariantCartPayload(product, variant, 2, variants);
    expect(line.variant_id).toBe(11);
    expect(line.quantity).toBe(2);
    expect(line.stock_quantity).toBe(5);
    expect(line.price).toBe(1600);
  });
});
