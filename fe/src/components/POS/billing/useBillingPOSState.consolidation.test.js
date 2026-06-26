import { renderHook, act, waitFor } from '@testing-library/react';
import { useBillingPOSState } from './useBillingPOSState';
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
  toast: { warning: jest.fn(), error: jest.fn(), success: jest.fn() },
}));

jest.mock('../../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => ({
    settings: {
      validate_stock_before_sale: false,
      require_customer: false,
      allow_partial_payment: false,
      show_discount: true,
      show_tax: true,
    },
  }),
}));

const PRODUCT = {
  id: 9,
  name: 'Soap',
  price: '80.00',
  selling_price: '80.00',
  stock_quantity: 50,
  track_stock: true,
  has_variants: false,
};

const DUPLICATE_HOLDING = {
  id: 7,
  sale_number: 'HOLD-007',
  subtotal: 240,
  tax_amount: 0,
  discount_amount: 0,
  items: [
    {
      product_id: 9,
      product_name: 'Soap',
      quantity: 2,
      unit_price: '80',
      product: { id: 9, name: 'Soap', stock_quantity: 50, track_stock: true },
    },
    {
      product_id: 9,
      product_name: 'Soap',
      quantity: 1,
      unit_price: '80',
      product: { id: 9, name: 'Soap', stock_quantity: 50, track_stock: true },
    },
  ],
};

async function bootHook() {
  const hook = renderHook(() => useBillingPOSState());
  await waitFor(() => expect(hook.result.current.loadingHolding).toBe(false));
  return hook;
}

describe('useBillingPOSState line consolidation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    customersAPI.list.mockResolvedValue({ data: { results: [] } });
    salesAPI.activeHolding.mockResolvedValue({ data: { holding: null } });
    salesAPI.saveHolding.mockResolvedValue({ data: { id: 42, sale_number: 'HOLD-042' } });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('saveHolding merges duplicate cart rows for the same product', async () => {
    const { result } = await bootHook();

    act(() => {
      result.current.addToCart(PRODUCT);
      result.current.addToCart(PRODUCT);
    });

    expect(result.current.cart).toHaveLength(1);
    expect(result.current.cart[0].quantity).toBe(2);

    await act(async () => {
      jest.advanceTimersByTime(700);
    });

    await waitFor(() => expect(salesAPI.saveHolding).toHaveBeenCalled());

    const payload = salesAPI.saveHolding.mock.calls.at(-1)[0];
    expect(payload.items).toEqual([
      {
        product_id: 9,
        variant_id: null,
        quantity: 2,
        unit_price: 80,
      },
    ]);
  });

  it('continueCartRecovery merges duplicate holding lines into one cart row', async () => {
    salesAPI.activeHolding.mockResolvedValue({ data: { holding: DUPLICATE_HOLDING } });

    const { result } = await bootHook();

    await waitFor(() => expect(result.current.cartRecovery).toBeTruthy());

    act(() => {
      result.current.continueCartRecovery();
    });

    await waitFor(() => expect(result.current.cart).toHaveLength(1));
    expect(result.current.cart[0].quantity).toBe(3);
  });
});
