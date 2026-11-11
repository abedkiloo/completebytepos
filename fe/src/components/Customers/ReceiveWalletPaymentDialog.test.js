import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ReceiveWalletPaymentDialog from './ReceiveWalletPaymentDialog';
import { customersAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { collectionPayerDetailsEnabled } from '../../utils/collectionPayer';

jest.mock('../../services/api', () => ({
  customersAPI: {
    walletTransactions: jest.fn(),
    receiveWalletPayment: jest.fn(),
  },
  paymentIntentsAPI: {
    create: jest.fn(),
    get: jest.fn(),
    stk: jest.fn(),
    query: jest.fn(),
  },
}));

jest.mock('../Payments/StkWaitDialog', () => ({
  __esModule: true,
  default: ({ open, onPaid }) =>
    open ? (
      <button
        type="button"
        onClick={() => onPaid({ mpesa_receipt: 'QHX7K2L9M1' })}
      >
        mock-stk-paid
      </button>
    ) : null,
}));

jest.mock('../../utils/toast', () => ({
  toast: { success: jest.fn(), error: jest.fn(), warning: jest.fn(), info: jest.fn() },
}));

jest.mock('../../utils/collectionPayer', () => {
  const actual = jest.requireActual('../../utils/collectionPayer');
  return {
    ...actual,
    collectionPayerDetailsEnabled: jest.fn(() => true),
  };
});

const debtor = {
  id: 3,
  name: 'Jane Debtor',
  wallet_balance: '-150.00',
  phone: '0712345678',
};

describe('ReceiveWalletPaymentDialog', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    collectionPayerDetailsEnabled.mockReturnValue(true);
    customersAPI.walletTransactions.mockResolvedValue({ data: [] });
    customersAPI.receiveWalletPayment.mockResolvedValue({
      data: { wallet_balance: '-50.00' },
    });
  });

  it('prefills full debt and submits cash without who-paid fields', async () => {
    const onSuccess = jest.fn();
    const onOpenChange = jest.fn();

    render(
      <ReceiveWalletPaymentDialog
        open
        customer={debtor}
        onOpenChange={onOpenChange}
        onSuccess={onSuccess}
      />
    );

    expect(screen.getByText(/Receive wallet payment/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText(/Payment amount/i)).toHaveValue(150);
    });
    expect(screen.queryByTestId('wallet-payer-name')).not.toBeInTheDocument();
    expect(screen.queryByTestId('wallet-payer-phone')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Record payment/i }));
    expect(
      await screen.findByText(/Proceed with this payment/i)
    ).toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button', { name: /Yes, record payment/i }));

    await waitFor(() => {
      expect(customersAPI.receiveWalletPayment).toHaveBeenCalledWith(3, {
        amount: 150,
        payment_method: 'cash',
        reference: '',
        notes: '',
      });
    });
    expect(onSuccess).toHaveBeenCalled();
  });

  it('asks who paid only after a non-cash method is selected', async () => {
    render(
      <ReceiveWalletPaymentDialog
        open
        customer={debtor}
        onOpenChange={jest.fn()}
        onSuccess={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Payment amount/i)).toHaveValue(150);
    });
    expect(screen.queryByTestId('wallet-payer-name')).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/Payment method/i), {
      target: { value: 'mpesa' },
    });
    expect(screen.getByTestId('wallet-payer-name')).toHaveValue('Jane Debtor');
    expect(screen.getByTestId('wallet-payer-phone')).toHaveValue('0712345678');
  });

  it('asks till or bank before allowing an M-Pesa code', async () => {
    render(
      <ReceiveWalletPaymentDialog
        open
        customer={debtor}
        onOpenChange={jest.fn()}
        onSuccess={jest.fn()}
      />
    );

    fireEvent.change(screen.getByLabelText(/Payment method/i), {
      target: { value: 'mpesa' },
    });
    expect(screen.getByTestId('mpesa-destination-step')).toBeInTheDocument();
    expect(screen.queryByLabelText(/M-Pesa code/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Record payment/i }));
    expect(customersAPI.receiveWalletPayment).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalled();

    fireEvent.click(screen.getByTestId('mpesa-destination-till'));
    expect(await screen.findByLabelText(/M-Pesa code/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/M-Pesa code/i), {
      target: { value: 'QHX7K2L9M1' },
    });
    const receipt = new File(['fake-jpeg'], 'receipt.jpg', { type: 'image/jpeg' });
    fireEvent.change(screen.getByTestId('wallet-receipt-image'), {
      target: { files: [receipt] },
    });
    fireEvent.click(screen.getByRole('button', { name: /Record payment/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Yes, record payment/i }));

    await waitFor(() => {
      expect(customersAPI.receiveWalletPayment).toHaveBeenCalled();
    });
    const [, payload] = customersAPI.receiveWalletPayment.mock.calls.at(-1);
    expect(payload).toBeInstanceOf(FormData);
    expect(payload.get('payment_method')).toBe('mpesa');
    expect(payload.get('reference')).toBe('QHX7K2L9M1');
    expect(payload.get('mpesa_destination')).toBe('till');
    expect(payload.get('receipt_image')).toBeTruthy();
  });

  it('requires an M-Pesa receipt screenshot before submit', async () => {
    render(
      <ReceiveWalletPaymentDialog
        open
        customer={debtor}
        onOpenChange={jest.fn()}
        onSuccess={jest.fn()}
      />
    );

    fireEvent.change(screen.getByLabelText(/Payment method/i), {
      target: { value: 'mpesa' },
    });
    fireEvent.click(screen.getByTestId('mpesa-destination-till'));
    fireEvent.change(await screen.findByLabelText(/M-Pesa code/i), {
      target: { value: 'QHX7K2L9M1' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Record payment/i }));
    expect(customersAPI.receiveWalletPayment).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith(
      'Attach a screenshot of the M-Pesa repayment receipt.'
    );
  });

  it('pay full debt button sets amount', async () => {
    render(
      <ReceiveWalletPaymentDialog
        open
        customer={debtor}
        onOpenChange={jest.fn()}
        onSuccess={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Payment amount/i)).toHaveValue(150);
    });

    fireEvent.change(screen.getByLabelText(/Payment amount/i), { target: { value: '20' } });
    fireEvent.click(screen.getByRole('button', { name: /Pay full debt/i }));
    expect(screen.getByLabelText(/Payment amount/i)).toHaveValue(150);
  });

  it('shows what amount is expected when the number is invalid', async () => {
    render(
      <ReceiveWalletPaymentDialog
        open
        customer={debtor}
        onOpenChange={jest.fn()}
        onSuccess={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Payment amount/i)).toHaveValue(150);
    });

    fireEvent.change(screen.getByLabelText(/Payment amount/i), {
      target: { value: '0' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Record payment/i }));

    expect(customersAPI.receiveWalletPayment).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith(
      'Amount must be greater than zero, e.g. 250.00'
    );
  });

  it('skips payer fields when the module feature is off', async () => {
    collectionPayerDetailsEnabled.mockReturnValue(false);
    render(
      <ReceiveWalletPaymentDialog
        open
        customer={debtor}
        onOpenChange={jest.fn()}
        onSuccess={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Payment amount/i)).toHaveValue(150);
    });
    expect(screen.queryByTestId('wallet-payer-name')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Record payment/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Yes, record payment/i }));

    await waitFor(() => {
      expect(customersAPI.receiveWalletPayment).toHaveBeenCalledWith(3, {
        amount: 150,
        payment_method: 'cash',
        reference: '',
        notes: '',
      });
    });
  });

  it('toasts pending approval when collection is queued', async () => {
    const onSuccess = jest.fn();
    const onOpenChange = jest.fn();
    customersAPI.receiveWalletPayment.mockResolvedValue({
      status: 202,
      data: {
        wallet_balance: '-150.00',
        pending_change: { id: 9, action_type: 'debt_collection' },
      },
    });

    render(
      <ReceiveWalletPaymentDialog
        open
        customer={debtor}
        onOpenChange={onOpenChange}
        onSuccess={onSuccess}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Record payment/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Yes, record payment/i }));

    await waitFor(() => {
      expect(toast.warning).toHaveBeenCalled();
    });
    expect(toast.success).not.toHaveBeenCalled();
    expect(onSuccess).toHaveBeenCalledWith(debtor);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('toasts an error when recording fails', async () => {
    customersAPI.receiveWalletPayment.mockRejectedValue({
      response: { data: { error: 'Wallet locked' } },
    });

    render(
      <ReceiveWalletPaymentDialog
        open
        customer={debtor}
        onOpenChange={jest.fn()}
        onSuccess={jest.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Record payment/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Yes, record payment/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Wallet locked');
    });
  });
});
