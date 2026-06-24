import { renderHook, act, waitFor } from '@testing-library/react';
import { usePOSState, cartItemKey } from './usePOSState';
import { buildVariantCartPayload } from '../../../utils/variantSelector';
import { normalizeModuleSettings } from '../../../utils/moduleCache';

jest.mock('../../../services/api', () => ({
  productsAPI: {
    list: jest.fn().mockResolvedValue({ data: { results: [] } }),
    search: jest.fn().mockResolvedValue({ data: [] }),
  },
  categoriesAPI: {
    list: jest.fn().mockResolvedValue({ data: { results: [] } }),
  },
  customersAPI: {
    list: jest.fn().mockResolvedValue({
      data: { results: [{ id: 'walk-in', name: 'Walk-in customer' }] },
    }),
  },
  salesAPI: {},
  authAPI: {
    me: jest.fn().mockResolvedValue({
      data: { user: { id: 9, username: 'cashier', profile: { branch_id: 2 } } },
    }),
  },
}));

jest.mock('../../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => ({
    settings: {
      validate_stock_before_sale: false,
      require_customer: false,
      allow_partial_payment: true,
      allow_excess_to_wallet: true,
      show_discount: true,
      show_tax: true,
      show_delivery: false,
    },
  }),
}));

function enableVariantsFeature() {
  localStorage.setItem(
    'enabled_modules',
    JSON.stringify(
      normalizeModuleSettings({
        products: {
          is_enabled: true,
          features: { product_variants: { is_enabled: true } },
        },
      })
    )
  );
}

const VARIANT_PRODUCT = {
  id: 7,
  name: 'Shirt',
  price: '100',
  selling_price: '100',
  stock_quantity: 20,
  track_stock: true,
  has_variants: true,
};

function variantLine(variantId, stock, qty = 1) {
  const product = { ...VARIANT_PRODUCT, id: 1, name: 'Webbing', price: '100' };
  return buildVariantCartPayload(
    product,
    {
      id: variantId,
      size: variantId === 10 ? 2 : 3,
      color: 5,
      size_name: variantId === 10 ? 'Large' : 'Medium',
      color_name: 'Blue',
      price: '100',
      stock_quantity: stock,
      sku: `WEB-${variantId}`,
    },
    qty
  );
}

describe('usePOSState variant cart', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    enableVariantsFeature();
    localStorage.setItem(
      'user',
      JSON.stringify({ id: 9, username: 'cashier', profile: { branch_id: 2 } })
    );
  });

  it('cartItemKey treats different variant_id values as distinct lines', () => {
    expect(cartItemKey({ id: 1, variant_id: 10 })).toBe('1-10');
    expect(cartItemKey({ id: 1, variant_id: 11 })).toBe('1-11');
    expect(cartItemKey({ id: 1 })).toBe('1');
    expect(cartItemKey({ id: 1, variant_id: 10 })).not.toBe(
      cartItemKey({ id: 1, variant_id: 11 })
    );
  });

  it('tryAddToCart opens variant picker when has_variants even without size/color attrs', async () => {
    const { result } = renderHook(() => usePOSState());

    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.tryAddToCart({
        ...VARIANT_PRODUCT,
        available_sizes_detail: undefined,
        available_colors_detail: undefined,
      });
    });

    expect(result.current.variantPickerProduct?.id).toBe(7);
    expect(result.current.cart).toHaveLength(0);
  });

  it('addProductToCart keeps separate lines for different variants of the same product', async () => {
    const { result } = renderHook(() => usePOSState());

    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.addProductToCart(variantLine(10, 5, 1));
      result.current.addProductToCart(variantLine(11, 8, 2));
    });

    expect(result.current.cart).toHaveLength(2);
    expect(result.current.cart.map((line) => line.variant_id).sort()).toEqual([10, 11]);
    expect(result.current.cart.find((l) => l.variant_id === 11)?.quantity).toBe(2);
  });

  it('addProductToCart merges quantity when the same variant is added again', async () => {
    const { result } = renderHook(() => usePOSState());

    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.addProductToCart(variantLine(10, 5, 1));
      result.current.addProductToCart(variantLine(10, 5, 3));
    });

    expect(result.current.cart).toHaveLength(1);
    expect(result.current.cart[0].variant_id).toBe(10);
    expect(result.current.cart[0].quantity).toBe(4);
  });
});
