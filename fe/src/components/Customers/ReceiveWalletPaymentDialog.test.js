import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ReceiveWalletPaymentDialog from './ReceiveWalletPaymentDialog';
import { customersAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  customersAPI: {
    walletTransactions: jest.fn(),
    receiveWalletPayment: jest.fn(),
  },
}));

const debtor = {
  id: 3,
  name: 'Jane Debtor',
  wallet_balance: '-150.00',
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

    fireEvent.click(screen.getByRole('button', { name: /Record payment/i }));

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
});
