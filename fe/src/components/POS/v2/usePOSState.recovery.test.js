import { renderHook, act, waitFor } from '@testing-library/react';
import { usePOSState } from './usePOSState';
import { salesAPI } from '../../../services/api';
import {
  posCartDraftKey,
  serializeRetailCartDraft,
  saveRetailCartDraft,
  clearRetailCartDraft,
} from '../../../utils/posCartRecovery';

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
  salesAPI: {
    activeHolding: jest.fn().mockResolvedValue({ data: { holding: null } }),
    saveHolding: jest.fn(),
    checkout: jest.fn(),
    create: jest.fn(),
    get: jest.fn(),
  },
  authAPI: {
    me: jest.fn().mockResolvedValue({
      data: { user: { id: 9, username: 'cashier', profile: { branch_id: 2 } } },
    }),
  },
}));

jest.mock('../../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => ({
    settings: {
      validate_stock_before_sale: true,
      require_customer: false,
      allow_partial_payment: true,
      allow_excess_to_wallet: true,
      show_discount: true,
      show_tax: true,
      show_delivery: false,
    },
  }),
}));

describe('usePOSState local cart recovery', () => {
  const draftKey = posCartDraftKey(9, 2);

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    localStorage.setItem(
      'user',
      JSON.stringify({ id: 9, username: 'cashier', profile: { branch_id: 2 } })
    );
    clearRetailCartDraft(draftKey);
  });

  it('prompts then restores retail cart from localStorage draft', async () => {
    saveRetailCartDraft(
      draftKey,
      serializeRetailCartDraft({
        cart: [
          {
            id: 5,
            name: 'Snacks',
            price: 120,
            quantity: 2,
            track_stock: true,
            stock_quantity: 50,
          },
        ],
        selectedCustomer: { id: 'walk-in', name: 'Walk-in customer' },
        taxPct: 0,
        discount: 0,
      })
    );

    const { result } = renderHook(() => usePOSState());

    await waitFor(() => {
      expect(result.current.cartRecovery).toBeTruthy();
    });

    expect(result.current.cartRecovery.itemCount).toBe(2);
    expect(result.current.cart).toHaveLength(0);

    act(() => {
      result.current.continueCartRecovery();
    });

    await waitFor(() => {
      expect(result.current.cart).toHaveLength(1);
    });

    expect(result.current.cart[0].name).toBe('Snacks');
    expect(result.current.cart[0].quantity).toBe(2);
    expect(result.current.cartRecovery).toBeNull();
  });

  it('prompts then restores a returned sale from the server holding', async () => {
    salesAPI.activeHolding.mockResolvedValueOnce({
      data: {
        holding: {
          id: 88,
          sale_number: 'S-RET',
          subtotal: '200.00',
          tax_amount: '0',
          discount_amount: '0',
          payment_method: 'cash',
          customer: null,
          items: [
            {
              product_id: 5,
              product: { id: 5, name: 'Milk', price: 100, stock_quantity: 20, track_stock: true },
              product_name: 'Milk',
              quantity: 2,
              unit_price: '100.00',
            },
          ],
        },
      },
    });

    const { result } = renderHook(() => usePOSState());

    await waitFor(() => {
      expect(result.current.cartRecovery).toBeTruthy();
    });
    expect(result.current.cartRecovery.source).toBe('holding');
    expect(result.current.cartRecovery.label).toBe('S-RET');

    act(() => {
      result.current.continueCartRecovery();
    });

    await waitFor(() => {
      expect(result.current.cart).toHaveLength(1);
    });
    expect(result.current.cart[0].name).toBe('Milk');
    expect(result.current.cart[0].quantity).toBe(2);
    expect(result.current.cartRecovery).toBeNull();
  });

  it('loads a specific returned sale from resumeSaleId', async () => {
    salesAPI.get.mockResolvedValueOnce({
      data: {
        id: 99,
        status: 'holding',
        needs_salesperson_action: true,
        rejection_reason: 'Wrong prices',
        sale_number: 'S-RET',
        subtotal: '200.00',
        tax_amount: '0',
        discount_amount: '0',
        payment_method: 'cash',
        customer: null,
        items: [
          {
            product_id: 5,
            product: { id: 5, name: 'Milk', price: 100, stock_quantity: 20, track_stock: true },
            product_name: 'Milk',
            quantity: 2,
            unit_price: '100.00',
          },
        ],
      },
    });

    const { result } = renderHook(() => usePOSState({ resumeSaleId: '99' }));

    await waitFor(() => {
      expect(result.current.cart).toHaveLength(1);
    });
    expect(salesAPI.get).toHaveBeenCalledWith(99);
    expect(salesAPI.activeHolding).not.toHaveBeenCalled();
    expect(result.current.cart[0].name).toBe('Milk');
    expect(result.current.returnedSaleNotice).toEqual({
      saleNumber: 'S-RET',
      comment: 'Wrong prices',
    });
  });
});
