import {
  findVariantForSelection,
  getSellableStockForVariant,
  canAddVariantToCart,
  isVariantAddToCartDisabled,
  buildVariantCartPayload,
  variantMatchesSize,
  getActiveVariants,
  getVariantPickerMode,
  getPickerSizes,
  getPickerColors,
  shouldOpenVariantPicker,
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

  it('shouldOpenVariantPicker when product has variants and feature is on', () => {
    localStorage.setItem(
      'enabled_modules',
      JSON.stringify({
        products: {
          is_enabled: true,
          features: { product_variants: { is_enabled: true } },
        },
      })
    );
    expect(shouldOpenVariantPicker({ has_variants: true })).toBe(true);
    expect(shouldOpenVariantPicker({ has_variants: false })).toBe(false);
    localStorage.clear();
  });

  it('getPickerColors only returns colors with a variant for the selected size', () => {
    const partialVariants = [
      { id: 10, size: 2, color: 5, size_name: 'Large', color_name: 'Blue' },
      { id: 11, size: 3, color: 6, size_name: 'Medium', color_name: 'Red' },
    ];
    const allColors = [
      { id: 5, name: 'Blue' },
      { id: 6, name: 'Red' },
      { id: 7, name: 'Green' },
    ];
    expect(getPickerColors(partialVariants, allColors, 2).map((c) => c.id)).toEqual([5]);
    expect(getPickerColors(partialVariants, allColors, 3).map((c) => c.id)).toEqual([6]);
  });

  it('getVariantPickerMode uses list when variants have no size or color', () => {
    const rows = [{ id: 1, sku: 'SKU-A' }, { id: 2, sku: 'SKU-B' }];
    expect(getVariantPickerMode(rows)).toBe('list');
    expect(getVariantPickerMode(variants)).toBe('size-color');
  });

  it('getPickerSizes only includes sizes present on variant rows', () => {
    const partialVariants = [
      { id: 10, size: 2, size_name: 'Large' },
      { id: 11, size: 3, size_name: 'Medium' },
    ];
    const allSizes = [
      { id: 2, name: 'Large', code: 'L' },
      { id: 3, name: 'Medium', code: 'M' },
      { id: 4, name: 'Small', code: 'S' },
    ];
    expect(getPickerSizes(partialVariants, allSizes).map((s) => s.id)).toEqual([2, 3]);
  });

  it('getActiveVariants skips inactive rows', () => {
    const rows = [
      { id: 1, is_active: true },
      { id: 2, is_active: false },
      { id: 3 },
    ];
    expect(getActiveVariants(rows).map((v) => v.id)).toEqual([1, 3]);
  });

  it('shouldOpenVariantPicker is false when feature is disabled', () => {
    localStorage.setItem(
      'enabled_modules',
      JSON.stringify({
        products: {
          is_enabled: true,
          features: { product_variants: { is_enabled: false } },
        },
      })
    );
    expect(shouldOpenVariantPicker({ has_variants: true })).toBe(false);
    localStorage.clear();
  });

  it('canAddVariantToCart requires selectedVariant in list picker mode', () => {
    const rows = [{ id: 99, sku: 'ONLY' }];
    expect(
      canAddVariantToCart({
        product,
        variants: rows,
        selectedSize: null,
        selectedColor: null,
        selectedVariant: null,
        availableSizes: [],
        availableColors: [],
      })
    ).toBe(false);
    expect(
      canAddVariantToCart({
        product,
        variants: rows,
        selectedSize: null,
        selectedColor: null,
        selectedVariant: rows[0],
        availableSizes: [],
        availableColors: [],
      })
    ).toBe(true);
  });

  it('buildVariantCartPayload assigns distinct variant_id per row', () => {
    const v10 = findVariantForSelection(variants, 2, 5, sizes, colors);
    const v11 = findVariantForSelection(variants, 3, 5, sizes, colors);
    const lineA = buildVariantCartPayload(product, v10, 1, variants);
    const lineB = buildVariantCartPayload(product, v11, 1, variants);
    expect(lineA.variant_id).toBe(10);
    expect(lineB.variant_id).toBe(11);
    expect(lineA.id).toBe(lineB.id);
    expect(lineA.variant_id).not.toBe(lineB.variant_id);
  });
});
