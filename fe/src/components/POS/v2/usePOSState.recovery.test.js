import { renderHook, act, waitFor } from '@testing-library/react';
import { usePOSState } from './usePOSState';
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
});
