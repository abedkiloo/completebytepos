import { renderHook, act, waitFor } from '@testing-library/react';
import { useBillingPOSState } from './useBillingPOSState';
import { customersAPI, salesAPI } from '../../../services/api';
import { toast } from '../../../utils/toast';
import { WALK_IN_CUSTOMER } from '../../../utils/walkInCustomer';

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

const PRODUCT = {
  id: 9,
  name: 'Soap',
  price: '80.00',
  selling_price: '80.00',
  stock_quantity: 50,
  track_stock: true,
  has_variants: false,
};

const CUSTOMER = { id: 3, name: 'Alice', phone: '0700111222' };

async function bootHook() {
  const hook = renderHook(() => useBillingPOSState());
  await waitFor(() => expect(hook.result.current.loadingHolding).toBe(false));
  return hook;
}

describe('useBillingPOSState checkout — payment on account', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    customersAPI.list.mockResolvedValue({
      data: { results: [CUSTOMER] },
    });
    salesAPI.activeHolding.mockResolvedValue({ data: { holding: null } });
    salesAPI.saveHolding.mockResolvedValue({ data: { id: 55, sale_number: 'HOLD-055' } });
    salesAPI.checkout.mockResolvedValue({
      data: { id: 99, total: '80.00', sale_number: 'S-99' },
    });
  });

  it('payFullAmountLater enables partial payment and sets amount to zero', async () => {
    const { result } = await bootHook();

    act(() => {
      result.current.setSelectedCustomer(CUSTOMER);
    });

    await waitFor(() => expect(result.current.partialPayment).toBe(false));

    act(() => {
      result.current.payFullAmountLater();
    });

    expect(result.current.partialPayment).toBe(true);
    expect(result.current.amountPaid).toBe('0');
  });

  it('checkout posts full pay-later sale when partial on and amount empty', async () => {
    const { result } = await bootHook();

    act(() => {
      result.current.addToCart(PRODUCT);
    });
    act(() => {
      result.current.setSelectedCustomer(CUSTOMER);
    });
    await waitFor(() =>
      expect(result.current.selectedCustomer).toMatchObject({ id: CUSTOMER.id })
    );
    act(() => {
      result.current.attemptSetPartialPayment(true);
    });
    await waitFor(() => expect(result.current.partialPayment).toBe(true));

    await act(async () => {
      await result.current.checkout();
    });

    expect(salesAPI.checkout).toHaveBeenCalledWith(
      55,
      expect.objectContaining({
        payment_method: 'cash',
        amount_paid: 0,
        allow_partial_payment: true,
      })
    );
    expect(toast.success).toHaveBeenCalledWith(
      'Sale completed. Full amount added to customer account.'
    );
  });

  it('checkout posts partial payment with balance on account', async () => {
    const { result } = await bootHook();

    act(() => {
      result.current.addToCart(PRODUCT);
    });
    act(() => {
      result.current.setSelectedCustomer(CUSTOMER);
    });
    await waitFor(() =>
      expect(result.current.selectedCustomer).toMatchObject({ id: CUSTOMER.id })
    );
    act(() => {
      result.current.attemptSetPartialPayment(true);
      result.current.setAmountPaid('30');
    });
    await waitFor(() => expect(result.current.partialPayment).toBe(true));

    await act(async () => {
      await result.current.checkout();
    });

    expect(salesAPI.checkout).toHaveBeenCalledWith(
      55,
      expect.objectContaining({
        amount_paid: 30,
        allow_partial_payment: true,
      })
    );
    expect(toast.success).toHaveBeenCalledWith(
      'Sale completed. Balance added to customer account.'
    );
  });

  it('blocks underpayment when payment on account is off', async () => {
    const { result } = await bootHook();

    act(() => {
      result.current.addToCart(PRODUCT);
      result.current.setSelectedCustomer(CUSTOMER);
      result.current.setAmountPaid('20');
    });

    await act(async () => {
      await result.current.checkout();
    });

    expect(salesAPI.checkout).not.toHaveBeenCalled();
    expect(toast.warning).toHaveBeenCalledWith(
      'Enable "Payment on customer account" for a partial payment or pay later.'
    );
  });

  it('prompts for customer when enabling payment on account for walk-in', async () => {
    const { result } = await bootHook();

    act(() => {
      result.current.setSelectedCustomer(WALK_IN_CUSTOMER);
      result.current.attemptSetPartialPayment(true);
    });

    expect(result.current.partialPayment).toBe(false);
    expect(result.current.partialPaymentCustomerPrompt).toBe(true);
  });
});
