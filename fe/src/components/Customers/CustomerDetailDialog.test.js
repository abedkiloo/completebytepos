import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import CustomerDetailDialog from './CustomerDetailDialog';
import { salesAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  salesAPI: {
    list: jest.fn(),
    receipt: jest.fn(),
    get: jest.fn(),
    refund: jest.fn(),
  },
  customersAPI: {
    walletTransactions: jest.fn(),
    receiveWalletPayment: jest.fn(),
  },
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: () => ({ permissions: [] }),
  isManagerOrAdminFromStorage: () => true,
}));

jest.mock('../Approvals/ChangeReasonField', () => ({
  __esModule: true,
  default: ({ value, onChange, label }) => (
    <label>
      {label}
      <input
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  ),
}));

jest.mock('./ReceiveWalletPaymentDialog', () => () => null);

const customer = {
  id: 5,
  name: 'Martha',
  email: 'martha@example.com',
  phone: '0700000000',
  city: 'Nairobi',
  country: 'Kenya',
  total_outstanding: '0',
  wallet_balance: '0',
  customer_type: 'individual',
};

describe('CustomerDetailDialog', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    salesAPI.list.mockResolvedValue({
      data: {
        count: 1,
        results: [
          {
            id: 99,
            sale_number: 'S-900',
            total: '500.00',
            amount_paid: '500.00',
            created_at: '2026-06-24T10:00:00Z',
            item_count: 1,
            payment_method: 'cash',
            refund_status: 'none',
          },
        ],
      },
    });
    salesAPI.receipt.mockResolvedValue({
      data: {
        id: 99,
        sale_number: 'S-900',
        status: 'completed',
        refund_status: 'none',
        total: '500',
        amount_paid: '500',
        subtotal: '500',
        tax_amount: '0',
        discount_amount: '0',
        change: '0',
        payment_method: 'cash',
        created_at: '2026-06-24T10:00:00Z',
        refundable_remaining: '500',
        items: [
          {
            id: 1,
            product_name: 'Shirt',
            quantity: 1,
            unit_price: '500',
            subtotal: '500',
          },
        ],
      },
    });
    salesAPI.get.mockResolvedValue({
      data: {
        id: 99,
        sale_number: 'S-900',
        status: 'completed',
        refund_status: 'none',
        total: '500',
        refundable_remaining: '500',
        items: [
          {
            id: 1,
            product_name: 'Shirt',
            quantity: 1,
            refundable_quantity: 1,
          },
        ],
      },
    });
    salesAPI.refund.mockResolvedValue({ data: { refund_number: 'RF-001' } });
  });

  it('lists customer sales and opens sale detail on click', async () => {
    render(
      <CustomerDetailDialog customer={customer} open onOpenChange={() => {}} />
    );

    expect(screen.getByText('Martha')).toBeInTheDocument();
    expect(screen.getByText('martha@example.com')).toBeInTheDocument();

    await waitFor(() => {
      expect(salesAPI.list).toHaveBeenCalledWith(
        expect.objectContaining({ customer_id: 5, status: 'completed' })
      );
    });

    fireEvent.click(await screen.findByText('S-900'));

    await waitFor(() => {
      expect(salesAPI.receipt).toHaveBeenCalledWith(99);
    });
    expect(await screen.findByText(/Sale — S-900/)).toBeInTheDocument();
    expect(screen.getByText('Shirt')).toBeInTheDocument();
  });

  it('submits refund from sale detail flow', async () => {
    const onCustomerUpdated = jest.fn();
    render(
      <CustomerDetailDialog
        customer={customer}
        open
        onOpenChange={() => {}}
        onCustomerUpdated={onCustomerUpdated}
      />
    );

    fireEvent.click(await screen.findByText('S-900'));
    await waitFor(() => expect(salesAPI.receipt).toHaveBeenCalled());

    fireEvent.click(await screen.findByRole('button', { name: /Void \/ Refund/i }));
    await waitFor(() => expect(salesAPI.get).toHaveBeenCalledWith(99));

    const reasonInput = await screen.findByLabelText(/Reason for void/i);
    fireEvent.change(reasonInput, {
      target: { value: 'Wrong item' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Confirm void/i }));

    await waitFor(() => {
      expect(salesAPI.refund).toHaveBeenCalledWith(99, {
        full: true,
        reason: 'Wrong item',
      });
    });
    expect(onCustomerUpdated).toHaveBeenCalled();
  });
});
