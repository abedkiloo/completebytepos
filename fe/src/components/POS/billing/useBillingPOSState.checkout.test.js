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

    expect(salesAPI.checkout).not.toHaveBeenCalled();
    expect(result.current.showSaleCommitConfirm).toBe(true);

    await act(async () => {
      await result.current.confirmCheckout();
    });

    expect(salesAPI.checkout).toHaveBeenCalledWith(
      55,
      expect.objectContaining({
        payment_method: 'on_account',
        amount_paid: 0,
        allow_partial_payment: true,
      })
    );
    expect(toast.success).toHaveBeenCalledWith(
      'Sale completed. Full amount recorded as debt.'
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

    expect(salesAPI.checkout).not.toHaveBeenCalled();

    await act(async () => {
      await result.current.confirmCheckout();
    });

    expect(salesAPI.checkout).toHaveBeenCalledWith(
      55,
      expect.objectContaining({
        amount_paid: 30,
        allow_partial_payment: true,
      })
    );
    expect(toast.success).toHaveBeenCalledWith(
      'Sale completed. Balance recorded as debt.'
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
      'Enable "Allow debt / partial payment" to record unpaid balance as debt.'
    );
  });

  it('checkout waits for the in-flight draft save and still sends 28', async () => {
    let releaseFirst;
    const firstSave = new Promise((resolve) => {
      releaseFirst = resolve;
    });
    let calls = 0;
    salesAPI.saveHolding.mockImplementation((payload) => {
      calls += 1;
      if (calls === 1) {
        return firstSave.then(() => ({
          data: { id: 55, sale_number: 'HOLD-055' },
        }));
      }
      return Promise.resolve({
        data: { id: 55, sale_number: 'HOLD-055', echoed: payload },
      });
    });

    const { result } = await bootHook();
    act(() => {
      result.current.addToCart(PRODUCT);
      result.current.setQty('9', 28);
    });

    await waitFor(
      () => expect(salesAPI.saveHolding).toHaveBeenCalledTimes(1),
      { timeout: 2000 },
    );

    let checkoutDone;
    act(() => {
      checkoutDone = result.current.checkout();
    });
    expect(salesAPI.saveHolding).toHaveBeenCalledTimes(1);

    releaseFirst();
    await act(async () => {
      await checkoutDone;
    });

    expect(salesAPI.saveHolding).toHaveBeenCalledTimes(2);
    const checkoutPayload = salesAPI.saveHolding.mock.calls[1][0];
    expect(checkoutPayload.items).toEqual([
      expect.objectContaining({ product_id: 9, quantity: 28 }),
    ]);
    expect(checkoutPayload.holding_id).toBe(55);
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
