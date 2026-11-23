import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import TransferSaleStaffDialog from './TransferSaleStaffDialog';
import { salesAPI } from '../../services/api';
import { toast } from '../../utils/toast';

jest.mock('../../services/api', () => ({
  salesAPI: {
    staffChoices: jest.fn(),
    transferStaff: jest.fn(),
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

const sale = {
  id: 4,
  sale_number: 'S-4',
  served_by: 2,
  served_by_name: 'Rita',
  cashier_name: 'Rita',
};

describe('TransferSaleStaffDialog', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    salesAPI.staffChoices.mockResolvedValue({
      data: [
        { id: 2, display_name: 'Rita', phone: '0711666009' },
        { id: 5, display_name: 'Paul' },
      ],
    });
    salesAPI.transferStaff.mockResolvedValue({ data: { to_staff_name: 'Paul' } });
  });

  it('moves the sale to the other salesperson and does not show a phone', async () => {
    render(
      <TransferSaleStaffDialog open sale={sale} onOpenChange={jest.fn()} />
    );
    fireEvent.change(screen.getByLabelText('Salesperson'), { target: { value: 'Paul' } });
    await waitFor(() => screen.getByRole('button', { name: 'Paul' }));
    expect(screen.queryByText('0711666009')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Rita' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Paul' }));
    fireEvent.click(screen.getByRole('button', { name: 'Move to this salesperson' }));
    await waitFor(() =>
      expect(salesAPI.transferStaff).toHaveBeenCalledWith(4, {
        user_id: 5,
        reason: '',
      })
    );
    expect(toast.success).toHaveBeenCalled();
  });
});
