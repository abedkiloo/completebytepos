import { renderHook, act, waitFor } from '@testing-library/react';
import { useBillingPOSState } from './useBillingPOSState';
import { customersAPI, salesAPI } from '../../../services/api';

jest.mock('../../../services/api', () => ({
  productsAPI: {
    search: jest.fn().mockResolvedValue({ data: [] }),
  },
  customersAPI: {
    list: jest.fn(),
  },
  salesAPI: {
    activeHolding: jest.fn(),
    saveHolding: jest.fn(),
    cancelHolding: jest.fn(),
    get: jest.fn(),
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
      validate_stock_before_sale: true,
      require_customer: false,
      allow_partial_payment: true,
      show_discount: true,
      show_tax: true,
    },
  }),
}));

const SAMPLE_HOLDING = {
  id: 42,
  sale_number: 'HOLD-042',
  subtotal: '200.00',
  tax_amount: '0',
  discount_amount: '0',
  customer: null,
  items: [
    {
      product_id: 7,
      product_name: 'Bottled Water',
      quantity: 3,
      unit_price: '50.00',
      product: {
        id: 7,
        name: 'Bottled Water',
        stock_quantity: 100,
        track_stock: true,
      },
    },
    {
      product_id: 8,
      product_name: 'Bread',
      quantity: 1,
      unit_price: '50.00',
      product: {
        id: 8,
        name: 'Bread',
        stock_quantity: 20,
        track_stock: true,
      },
    },
  ],
};

describe('useBillingPOSState cart recovery', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    customersAPI.list.mockResolvedValue({
      data: { results: [{ id: 1, name: 'Jane', phone: '0700' }] },
    });
    salesAPI.saveHolding.mockResolvedValue({ data: { id: 42, sale_number: 'HOLD-042' } });
    salesAPI.cancelHolding.mockResolvedValue({ data: {} });
  });

  it('prompts for recovery then restores cart lines with quantities on continue', async () => {
    salesAPI.activeHolding.mockResolvedValue({ data: { holding: SAMPLE_HOLDING } });

    const { result } = renderHook(() => useBillingPOSState());

    await waitFor(() => {
      expect(result.current.cartRecovery).toBeTruthy();
    });

    expect(result.current.cartRecovery.itemCount).toBe(4);
    expect(result.current.cart).toHaveLength(0);

    act(() => {
      result.current.continueCartRecovery();
    });

    await waitFor(() => {
      expect(result.current.cart).toHaveLength(2);
    });

    expect(result.current.cart[0].name).toBe('Bottled Water');
    expect(result.current.cart[0].quantity).toBe(3);
    expect(result.current.cart[1].name).toBe('Bread');
    expect(result.current.cart[1].quantity).toBe(1);
    expect(result.current.holdingNumber).toBe('HOLD-042');
    expect(result.current.cartRecovery).toBeNull();
  });

  it('loads a specific returned sale from resumeSaleId on Terminal POS', async () => {
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
        total: '200.00',
        amount_paid: '40.00',
        payment_method: 'mpesa',
        payment_reference: 'QHX7K2L9M1',
        customer: null,
        items: [
          {
            product_id: 7,
            product: {
              id: 7,
              name: 'Bottled Water',
              price: 50,
              stock_quantity: 100,
              track_stock: true,
            },
            product_name: 'Bottled Water',
            quantity: 3,
            unit_price: '50.00',
          },
        ],
      },
    });

    const { result } = renderHook(() => useBillingPOSState({ resumeSaleId: '99' }));

    await waitFor(() => {
      expect(result.current.cart).toHaveLength(1);
    });
    expect(salesAPI.get).toHaveBeenCalledWith(99);
    expect(salesAPI.activeHolding).not.toHaveBeenCalled();
    expect(result.current.cart[0].name).toBe('Bottled Water');
    expect(result.current.cart[0].quantity).toBe(3);
    expect(result.current.returnedSaleNotice).toEqual({
      saleNumber: 'S-RET',
      comment: 'Wrong prices',
    });
    expect(result.current.amountPaid).toBe('40');
    expect(result.current.paymentMethod).toBe('mpesa');
    expect(result.current.paymentReference).toBe('QHX7K2L9M1');
  });

  it('loads returned sale lines even when on-hand stock is zero', async () => {
    salesAPI.get.mockResolvedValueOnce({
      data: {
        id: 77,
        status: 'holding',
        needs_salesperson_action: true,
        rejection_reason: 'Fix quantity',
        sale_number: 'S-ZERO',
        subtotal: '50.00',
        tax_amount: '0',
        discount_amount: '0',
        payment_method: 'cash',
        customer: null,
        items: [
          {
            product_id: 7,
            product: {
              id: 7,
              name: 'Bottled Water',
              price: 50,
              stock_quantity: 0,
              track_stock: true,
            },
            product_name: 'Bottled Water',
            quantity: 3,
            unit_price: '50.00',
          },
        ],
      },
    });

    const { result } = renderHook(() => useBillingPOSState({ resumeSaleId: '77' }));

    await waitFor(() => {
      expect(result.current.cart).toHaveLength(1);
    });
    expect(result.current.cart[0].name).toBe('Bottled Water');
    expect(result.current.cart[0].quantity).toBe(3);
  });

  it('start new sale cancels holding and clears recovery state', async () => {
    salesAPI.activeHolding.mockResolvedValue({ data: { holding: SAMPLE_HOLDING } });

    const { result } = renderHook(() => useBillingPOSState());

    await waitFor(() => {
      expect(result.current.cartRecovery).toBeTruthy();
    });

    await act(async () => {
      await result.current.startNewSaleFromRecovery();
    });

    expect(salesAPI.cancelHolding).toHaveBeenCalledWith(42);
    expect(result.current.cart).toHaveLength(0);
    expect(result.current.cartRecovery).toBeNull();
  });

  it('does not re-prompt continue-sale after Continue when searching customers', async () => {
    salesAPI.activeHolding.mockResolvedValue({ data: { holding: SAMPLE_HOLDING } });

    const { result } = renderHook(() => useBillingPOSState());

    await waitFor(() => {
      expect(result.current.cartRecovery).toBeTruthy();
    });

    act(() => {
      result.current.continueCartRecovery();
    });

    await waitFor(() => {
      expect(result.current.cartRecovery).toBeNull();
    });

    const callsAfterContinue = salesAPI.activeHolding.mock.calls.length;

    customersAPI.list.mockResolvedValue({
      data: {
        results: [
          { id: 1, name: 'Jane', phone: '0700' },
          { id: 2, name: 'New Duka', owner_name: 'Wanjiku', phone: '0711' },
        ],
      },
    });

    await act(async () => {
      result.current.setCustomerQuery('Wanjiku');
    });

    await waitFor(() => {
      expect(customersAPI.list).toHaveBeenCalledWith(
        expect.objectContaining({ search: 'Wanjiku' })
      );
    });

    expect(result.current.cartRecovery).toBeNull();
    expect(salesAPI.activeHolding.mock.calls.length).toBe(callsAfterContinue);
  });
});
