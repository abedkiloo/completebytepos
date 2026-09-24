import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ReceiveWalletPaymentDialog from './ReceiveWalletPaymentDialog';
import { customersAPI } from '../../services/api';
import { toast } from '../../utils/toast';

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

const debtor = {
  id: 3,
  name: 'Jane Debtor',
  wallet_balance: '-150.00',
  phone: '0712345678',
};

describe('ReceiveWalletPaymentDialog', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    customersAPI.walletTransactions.mockResolvedValue({ data: [] });
    customersAPI.receiveWalletPayment.mockResolvedValue({
      data: { wallet_balance: '-50.00' },
    });
  });

  it('prefills full debt and submits payment', async () => {
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
    expect(
      screen.getByText(/KES amount with up to 2 decimal places, e.g. 250.00/i)
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Record payment/i }));
    expect(
      await screen.findByText(/Proceed with this payment/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Do you really want to continue with this transaction/i)
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
    expect(screen.getByText(/greater than zero, e.g. 250.00/i)).toBeInTheDocument();
  });

  it('requires an M-Pesa receipt code before recording', async () => {
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
    fireEvent.click(screen.getByTestId('mpesa-capture-code'));
    expect(screen.getByLabelText(/M-Pesa code/i)).toBeInTheDocument();
    expect(
      screen.getByText(/At least 4 letters and numbers from the M-Pesa SMS/i)
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Record payment/i }));
    expect(customersAPI.receiveWalletPayment).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith(
      'Enter the M-Pesa code from the SMS (at least 4 letters and numbers), e.g. QHX7K2L9M1'
    );
    expect(
      screen.getByText(/Enter the M-Pesa code from the SMS \(at least 4 letters and numbers\)/i)
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/M-Pesa code/i), {
      target: { value: 'AB1' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Record payment/i }));
    expect(toast.error).toHaveBeenCalledWith(
      'Must be at least 4 characters (you entered 3), e.g. QHX7K2L9M1'
    );
    expect(screen.getByText(/you entered 3/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/M-Pesa code/i), {
      target: { value: ' qhx 7k2 l9m1 ' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Record payment/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Yes, record payment/i }));

    await waitFor(() => {
      expect(customersAPI.receiveWalletPayment).toHaveBeenCalledWith(3, {
        amount: 150,
        payment_method: 'mpesa',
        reference: 'QHX7K2L9M1',
        notes: '',
      });
    });
  });

  it('records an M-Pesa wallet payment after a prompt confirms', async () => {
    const onSuccess = jest.fn();
    render(
      <ReceiveWalletPaymentDialog
        open
        customer={debtor}
        onOpenChange={jest.fn()}
        onSuccess={onSuccess}
      />
    );

    fireEvent.change(screen.getByLabelText(/Payment method/i), {
      target: { value: 'mpesa' },
    });
    expect(screen.getByLabelText(/Safaricom number/i)).toHaveValue('0712345678');
    fireEvent.click(screen.getByRole('button', { name: /Record payment/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Yes, record payment/i }));
    fireEvent.click(await screen.findByText('mock-stk-paid'));

    await waitFor(() => {
      expect(customersAPI.receiveWalletPayment).toHaveBeenCalledWith(3, {
        amount: 150,
        payment_method: 'mpesa',
        reference: 'QHX7K2L9M1',
        notes: '',
      });
    });
    expect(onSuccess).toHaveBeenCalled();
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
