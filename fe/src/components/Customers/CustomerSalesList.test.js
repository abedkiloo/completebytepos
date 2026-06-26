import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import CustomerSalesList from './CustomerSalesList';
import { salesAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  salesAPI: {
    list: jest.fn(),
  },
}));

describe('CustomerSalesList', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('loads paginated sales and calls onSelectSale', async () => {
    salesAPI.list.mockResolvedValue({
      data: {
        count: 1,
        results: [
          {
            id: 7,
            sale_number: 'S-200',
            total: '1200.00',
            amount_paid: '600.00',
            created_at: '2026-06-24T12:00:00Z',
            item_count: 2,
            payment_method: 'cash',
            refund_status: 'none',
          },
        ],
      },
    });
    const onSelectSale = jest.fn();

    render(<CustomerSalesList customerId={3} onSelectSale={onSelectSale} />);

    await waitFor(() => {
      expect(salesAPI.list).toHaveBeenCalledWith(
        expect.objectContaining({ customer_id: 3, status: 'completed' })
      );
    });

    fireEvent.click(await screen.findByText('S-200'));
    expect(onSelectSale).toHaveBeenCalledWith(
      expect.objectContaining({ sale_number: 'S-200' })
    );
    expect(screen.getByText(/Balance/)).toBeInTheDocument();
  });
});
