import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import CustomerRecentSales from './CustomerRecentSales';
import { salesAPI } from '../../../services/api';

jest.mock('../../../services/api', () => ({
  salesAPI: {
    list: jest.fn(),
  },
}));

describe('CustomerRecentSales', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('loads completed sales for the selected customer', async () => {
    salesAPI.list.mockResolvedValue({
      data: {
        results: [
          {
            id: 1,
            sale_number: 'S-100',
            total: '500.00',
            created_at: '2026-06-24T10:00:00Z',
            item_count: 3,
            items: [
              {
                id: 10,
                product_name: 'Zipper',
                quantity: 2,
                unit_price: '200',
                subtotal: '400',
                size_name: 'Large',
                color_name: 'White',
              },
            ],
          },
        ],
      },
    });

    render(<CustomerRecentSales customerId={5} />);

    await waitFor(() => {
      expect(salesAPI.list).toHaveBeenCalledWith({
        customer_id: 5,
        status: 'completed',
        page_size: 10,
      });
    });

    expect(await screen.findByText('S-100')).toBeInTheDocument();
    expect(screen.getByText(/3 items/)).toBeInTheDocument();
  });

  it('expands a sale to show line items with variant labels', async () => {
    salesAPI.list.mockResolvedValue({
      data: {
        results: [
          {
            id: 1,
            sale_number: 'S-100',
            total: '400.00',
            created_at: '2026-06-24T10:00:00Z',
            item_count: 2,
            items: [
              {
                id: 10,
                product_name: 'Zipper',
                quantity: 2,
                unit_price: '200',
                subtotal: '400',
                size_name: 'Large',
                color_name: 'White',
              },
            ],
          },
        ],
      },
    });

    render(<CustomerRecentSales customerId={5} />);

    const row = await screen.findByText('S-100');
    fireEvent.click(row);

    expect(await screen.findByText('Large / White')).toBeInTheDocument();
    expect(screen.getByText(/Zipper/)).toBeInTheDocument();
  });

  it('renders nothing when no customer id', () => {
    const { container } = render(<CustomerRecentSales customerId={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
