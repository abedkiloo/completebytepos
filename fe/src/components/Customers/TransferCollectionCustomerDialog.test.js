import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import TransferCollectionCustomerDialog from './TransferCollectionCustomerDialog';
import { customersAPI } from '../../services/api';
import { toast } from '../../utils/toast';

jest.mock('../../services/api', () => ({
  customersAPI: {
    list: jest.fn(),
    transferWalletSettlementCustomer: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock('../ui/dialog', () => ({
  Dialog: ({ open, children }) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <h2>{children}</h2>,
  DialogDescription: ({ children }) => <p>{children}</p>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));

const collection = {
  id: 12,
  amount: '14000.00',
  customer_name: 'Wrong Shop',
  customer_id: 3,
};

describe('TransferCollectionCustomerDialog', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    customersAPI.list.mockResolvedValue({
      data: {
        results: [
          { id: 3, name: 'Wrong Shop', phone: '0711999001' },
          { id: 9, name: 'Right Shop', phone: '0711999002' },
        ],
      },
    });
    customersAPI.transferWalletSettlementCustomer.mockResolvedValue({ data: {} });
  });

  it('moves only this payment, and does not list the current customer', async () => {
    render(
      <TransferCollectionCustomerDialog
        open
        collection={collection}
        onOpenChange={jest.fn()}
        onSaved={jest.fn()}
      />
    );

    fireEvent.change(screen.getByLabelText('Correct customer'), {
      target: { value: 'Right' },
    });

    await waitFor(() => expect(customersAPI.list).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: 'Wrong Shop' })).not.toBeInTheDocument();
    expect(screen.queryByText('0711999002')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Right Shop' }));
    fireEvent.click(screen.getByRole('button', { name: 'Move this payment' }));

    await waitFor(() =>
      expect(customersAPI.transferWalletSettlementCustomer).toHaveBeenCalledWith(12, {
        customer_id: 9,
        move_sales: false,
        send_sms: false,
        reason: '',
      })
    );
    expect(toast.success).toHaveBeenCalled();
  });

  it('can move only the repayment when the sales are already correct', async () => {
    render(
      <TransferCollectionCustomerDialog
        open
        collection={collection}
        onOpenChange={jest.fn()}
      />
    );
    fireEvent.change(screen.getByLabelText('Correct customer'), {
      target: { value: 'Right' },
    });
    await waitFor(() => screen.getByRole('button', { name: 'Right Shop' }));
    fireEvent.click(screen.getByRole('button', { name: 'Right Shop' }));
    fireEvent.click(screen.getByTestId('transfer-move-sales'));
    fireEvent.click(screen.getByTestId('transfer-send-sms'));
    fireEvent.click(screen.getByRole('button', { name: 'Move this payment' }));
    await waitFor(() =>
      expect(customersAPI.transferWalletSettlementCustomer).toHaveBeenCalledWith(
        12,
        expect.objectContaining({ customer_id: 9, move_sales: true, send_sms: true })
      )
    );
  });
});
