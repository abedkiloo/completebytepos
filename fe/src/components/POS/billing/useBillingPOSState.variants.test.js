import { renderHook, act, waitFor } from '@testing-library/react';
import { useBillingPOSState } from './useBillingPOSState';
import { cartItemKey } from '../v2/usePOSState';
import { normalizeModuleSettings } from '../../../utils/moduleCache';
import { customersAPI, salesAPI } from '../../../services/api';

jest.mock('../../../services/api', () => ({
  productsAPI: {
    list: jest.fn().mockResolvedValue({ data: [] }),
  },
  customersAPI: {
    list: jest.fn(),
  },
  salesAPI: {
    activeHolding: jest.fn(),
    saveHolding: jest.fn(),
    cancelHolding: jest.fn(),
    checkout: jest.fn(),
  },
}));

jest.mock('../../../utils/toast', () => ({
  toast: {
    warning: jest.fn(),
    error: jest.fn(),
    success: jest.fn(),
  },
}));

jest.mock('../../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => ({
    settings: {
      validate_stock_before_sale: false,
      require_customer: false,
      allow_partial_payment: true,
      show_discount: true,
      show_tax: true,
    },
  }),
}));

const VARIANT_PRODUCT = {
  id: 12,
  name: 'Jacket',
  price: '250',
  selling_price: '250',
  stock_quantity: 30,
  track_stock: true,
  has_variants: true,
};

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

async function bootHook() {
  const hook = renderHook(() => useBillingPOSState());
  await waitFor(() => expect(hook.result.current.loadingHolding).toBe(false));
  return hook;
}

describe('useBillingPOSState variant cart', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    enableVariantsFeature();
    customersAPI.list.mockResolvedValue({ data: { results: [] } });
    salesAPI.activeHolding.mockResolvedValue({ data: { holding: null } });
    salesAPI.saveHolding.mockResolvedValue({ data: { id: 1, sale_number: 'HOLD-1' } });
  });

  it('addToCart opens variant picker for has_variants without catalog size/color fields', async () => {
    const { result } = await bootHook();

    act(() => {
      result.current.addToCart({
        ...VARIANT_PRODUCT,
        available_sizes_detail: [],
        available_colors_detail: [],
      });
    });

    expect(result.current.variantPickerProduct?.id).toBe(12);
    expect(result.current.cart).toHaveLength(0);
  });

  it('addToCart keeps separate billing lines per variant_id', async () => {
    const { result } = await bootHook();

    act(() => {
      result.current.addToCart(VARIANT_PRODUCT, {
        variant_id: 21,
        variant: { id: 21, sku: 'J-L', stock_quantity: 4, price: '250' },
        price: 250,
        quantity: 1,
      });
      result.current.addToCart(VARIANT_PRODUCT, {
        variant_id: 22,
        variant: { id: 22, sku: 'J-M', stock_quantity: 6, price: '240' },
        price: 240,
        quantity: 1,
      });
    });

    expect(result.current.cart).toHaveLength(2);
    expect(cartItemKey(result.current.cart[0])).not.toBe(
      cartItemKey(result.current.cart[1])
    );
    expect(result.current.cart.map((line) => line.variant_id).sort()).toEqual([21, 22]);
  });

  it('addToCart keeps variant size and color on cart lines', async () => {
    const { result } = await bootHook();

    act(() => {
      result.current.addToCart(VARIANT_PRODUCT, {
        variant_id: 21,
        variant: {
          id: 21,
          sku: 'J-L',
          size_name: 'Large',
          color_name: 'White',
          stock_quantity: 4,
          price: '250',
        },
        size: 'Large',
        color: 'White',
        price: 250,
        quantity: 1,
      });
    });

    expect(result.current.cart[0].size_name).toBe('Large');
    expect(result.current.cart[0].color_name).toBe('White');
    expect(result.current.cart[0].variant).toEqual(
      expect.objectContaining({ size_name: 'Large', color_name: 'White' })
    );
  });

  it('addToCart increments quantity when the same variant is added twice', async () => {
    const { result } = await bootHook();

    act(() => {
      result.current.addToCart(VARIANT_PRODUCT, {
        variant_id: 21,
        variant: { id: 21, sku: 'J-L', stock_quantity: 10, price: '250' },
        price: 250,
        quantity: 1,
      });
      result.current.addToCart(VARIANT_PRODUCT, {
        variant_id: 21,
        variant: { id: 21, sku: 'J-L', stock_quantity: 10, price: '250' },
        price: 250,
        quantity: 1,
      });
    });

    expect(result.current.cart).toHaveLength(1);
    expect(result.current.cart[0].variant_id).toBe(21);
    expect(result.current.cart[0].quantity).toBe(2);
  });
});
