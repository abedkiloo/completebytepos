import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';

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
    const onSaved = jest.fn();
    render(
      <TransferSaleStaffDialog open sale={sale} onOpenChange={jest.fn()} onSaved={onSaved} />
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
    expect(onSaved).toHaveBeenCalled();
  });

  it('keeps the list empty when the search fails or the box is cleared', async () => {
    salesAPI.staffChoices.mockRejectedValueOnce(new Error('down'));
    render(
      <TransferSaleStaffDialog open sale={sale} onOpenChange={jest.fn()} />
    );
    fireEvent.change(screen.getByLabelText('Salesperson'), { target: { value: 'Paul' } });
    await waitFor(() => expect(salesAPI.staffChoices).toHaveBeenCalledWith('Paul'));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Paul' })).not.toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('Salesperson'), { target: { value: '   ' } });
    expect(screen.queryByRole('button', { name: 'Paul' })).not.toBeInTheDocument();
  });

  it('drops a search error that arrives after the name changes', async () => {
    let failFirst;
    salesAPI.staffChoices.mockImplementationOnce(
      () => new Promise((_, reject) => { failFirst = reject; })
    );
    render(
      <TransferSaleStaffDialog open sale={sale} onOpenChange={jest.fn()} />
    );
    fireEvent.change(screen.getByLabelText('Salesperson'), { target: { value: 'Ann' } });
    await waitFor(() => expect(salesAPI.staffChoices).toHaveBeenCalledWith('Ann'));
    salesAPI.staffChoices.mockResolvedValueOnce({ data: [] });
    fireEvent.change(screen.getByLabelText('Salesperson'), { target: { value: 'Bea' } });
    await act(async () => { failFirst(new Error('late')); });
    await waitFor(() => expect(salesAPI.staffChoices).toHaveBeenCalledWith('Bea'));
    expect(screen.queryByRole('button', { name: 'Ann' })).not.toBeInTheDocument();
  });

  it('ignores a late search after the name changes', async () => {
    let finishFirst;
    salesAPI.staffChoices.mockImplementationOnce(
      () => new Promise((resolve) => { finishFirst = resolve; })
    );
    render(
      <TransferSaleStaffDialog open sale={sale} onOpenChange={jest.fn()} />
    );
    fireEvent.change(screen.getByLabelText('Salesperson'), { target: { value: 'Ann' } });
    await waitFor(() => expect(salesAPI.staffChoices).toHaveBeenCalledWith('Ann'));
    salesAPI.staffChoices.mockResolvedValueOnce({ data: { id: 9 } });
    fireEvent.change(screen.getByLabelText('Salesperson'), { target: { value: 'Bea' } });
    await act(async () => {
      finishFirst({ data: [{ id: 8, display_name: 'Ann' }] });
    });
    await waitFor(() => expect(salesAPI.staffChoices).toHaveBeenCalledWith('Bea'));
    expect(screen.queryByRole('button', { name: 'Ann' })).not.toBeInTheDocument();
  });

  it('shows the cashier when the sale has no number and reports a locked month', async () => {
    const onOpenChange = jest.fn();
    const onSaved = jest.fn();
    salesAPI.transferStaff.mockRejectedValueOnce({
      response: { data: { error: 'That month’s pay is already locked. Unlock it before moving this sale.' } },
    });
    render(
      <TransferSaleStaffDialog
        open
        sale={{ id: 4, sale_number: 'S-9', cashier: 2, cashier_name: 'Rita' }}
        onOpenChange={onOpenChange}
        onSaved={onSaved}
      />
    );
    expect(screen.getByText(/S-9 is with Rita/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Note (optional)'), { target: { value: '  Wrong person  ' } });
    fireEvent.change(screen.getByLabelText('Salesperson'), { target: { value: 'Paul' } });
    await waitFor(() => screen.getByRole('button', { name: 'Paul' }));
    fireEvent.click(screen.getByRole('button', { name: 'Paul' }));
    fireEvent.click(screen.getByRole('button', { name: 'Move to this salesperson' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(
      'That month’s pay is already locked. Unlock it before moving this sale.'
    ));
    expect(onSaved).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('asks for a salesperson when the sale has no id', async () => {
    render(
      <TransferSaleStaffDialog
        open
        sale={{ sale_number: 'S-0' }}
        onOpenChange={jest.fn()}
      />
    );
    expect(screen.getByText(/S-0 is with the current salesperson/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Salesperson'), { target: { value: 'Paul' } });
    await waitFor(() => screen.getByRole('button', { name: 'Paul' }));
    fireEvent.click(screen.getByRole('button', { name: 'Paul' }));
    fireEvent.click(screen.getByRole('button', { name: 'Move to this salesperson' }));
    expect(toast.error).toHaveBeenCalledWith('Choose the salesperson who should have this sale.');
    expect(salesAPI.transferStaff).not.toHaveBeenCalled();
  });

  it('hides a non-text error and waits while the move is saving', async () => {
    let finish;
    salesAPI.transferStaff.mockImplementationOnce(
      () => new Promise((resolve) => { finish = resolve; })
    );
    render(
      <TransferSaleStaffDialog open sale={sale} onOpenChange={jest.fn()} />
    );
    fireEvent.change(screen.getByLabelText('Salesperson'), { target: { value: 'Paul' } });
    await waitFor(() => screen.getByRole('button', { name: 'Paul' }));
    fireEvent.click(screen.getByRole('button', { name: 'Paul' }));
    fireEvent.click(screen.getByRole('button', { name: 'Move to this salesperson' }));
    await waitFor(() => expect(
      screen.getByRole('button', { name: 'Move to this salesperson' })
    ).toBeDisabled());
    await act(async () => { finish({ data: {} }); });

    salesAPI.transferStaff.mockRejectedValueOnce({ response: { data: { error: ['no'] } } });
    fireEvent.click(screen.getByRole('button', { name: 'Move to this salesperson' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Could not move this sale.'));

    salesAPI.transferStaff.mockRejectedValueOnce(new Error('down'));
    fireEvent.click(screen.getByRole('button', { name: 'Move to this salesperson' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(2));
  });

  it('stays closed until an admin opens it', () => {
    render(
      <TransferSaleStaffDialog open={false} sale={null} onOpenChange={jest.fn()} />
    );
    expect(screen.queryByLabelText('Salesperson')).not.toBeInTheDocument();
  });
});
