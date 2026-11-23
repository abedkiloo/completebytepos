import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import TransferSaleCustomerDialog from './TransferSaleCustomerDialog';
import { customersAPI, salesAPI } from '../../services/api';
import { toast } from '../../utils/toast';

jest.mock('../../services/api', () => ({
  customersAPI: { list: jest.fn() },
  salesAPI: { transferCustomer: jest.fn() },
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

const sale = {
  id: 4,
  sale_number: 'S-4',
  total: '800.00',
  customer_name: 'Customer Four',
  customer_id: 4,
};

describe('TransferSaleCustomerDialog', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    customersAPI.list.mockResolvedValue({
      data: {
        results: [
          { id: 4, name: 'Customer Four', phone: '0711888004' },
          { id: 3, name: 'Customer Three', phone: '0711888003' },
        ],
      },
    });
    salesAPI.transferCustomer.mockResolvedValue({ data: { sms_sent: false } });
  });

  it('moves only this sale and does not show phone numbers', async () => {
    render(
      <TransferSaleCustomerDialog open sale={sale} onOpenChange={jest.fn()} />
    );
    fireEvent.change(screen.getByLabelText('Correct customer'), {
      target: { value: 'Three' },
    });
    await waitFor(() => screen.getByRole('button', { name: 'Customer Three' }));
    expect(screen.queryByText('0711888003')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Customer Four' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Customer Three' }));
    fireEvent.click(screen.getByTestId('sale-transfer-send-sms'));
    fireEvent.click(screen.getByRole('button', { name: 'Move this sale' }));
    await waitFor(() =>
      expect(salesAPI.transferCustomer).toHaveBeenCalledWith(4, {
        customer_id: 3,
        send_sms: true,
        reason: '',
      })
    );
    expect(toast.success).toHaveBeenCalled();
  });
});
