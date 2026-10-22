import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import StockHistoryModal from './StockHistoryModal';
import { inventoryAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  inventoryAPI: { productHistory: jest.fn() },
}));

describe('StockHistoryModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('loads product history directly when there are no variants', async () => {
    inventoryAPI.productHistory.mockResolvedValue({
      data: [
        {
          id: 1,
          movement_type: 'sale',
          quantity: 2,
          stock_delta: -2,
          stock_flow: 'Previous stock 10 · Sold 2 · New stock 8',
          created_at: '2026-10-06T10:00:00Z',
        },
      ],
    });

    render(
      <StockHistoryModal
        embedded
        product={{ id: 7, name: 'Soap', has_variants: false, variants: [] }}
      />
    );

    await waitFor(() =>
      expect(screen.getByText(/Previous stock 10 · Sold 2 · New stock 8/)).toBeInTheDocument()
    );
    expect(inventoryAPI.productHistory).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ page: 1, page_size: 50 }),
    );
    expect(screen.queryByTestId('stock-history-variant-picker')).not.toBeInTheDocument();
  });

  it('reads paginated results and shows a real API error message', async () => {
    inventoryAPI.productHistory
      .mockResolvedValueOnce({
        data: {
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 3,
              movement_type: 'adjustment',
              quantity: 5,
              stock_delta: 5,
              stock_flow: 'Previous stock 0 · Adjusted +5 · New stock 5',
              created_at: '2026-10-06T10:00:00Z',
            },
          ],
        },
      })
      .mockRejectedValueOnce({
        response: { status: 500, data: { error: 'Database blew up' } },
      });

    const { rerender } = render(
      <StockHistoryModal
        embedded
        product={{ id: 8, name: 'Rope', has_variants: false, variants: [] }}
      />
    );

    await waitFor(() =>
      expect(screen.getByText(/Adjusted \+5/)).toBeInTheDocument()
    );

    inventoryAPI.productHistory.mockRejectedValueOnce({
      response: { status: 500, data: { error: 'Database blew up' } },
    });
    rerender(
      <StockHistoryModal
        embedded
        product={{ id: 9, name: 'Cable', has_variants: false, variants: [] }}
      />
    );

    await waitFor(() => expect(screen.getByText('Database blew up')).toBeInTheDocument());
    expect(
      screen.queryByText(/Admins only when enabled/i)
    ).not.toBeInTheDocument();
  });

  it('requires selecting a variant before loading history', async () => {
    inventoryAPI.productHistory.mockResolvedValue({
      data: [
        {
          id: 9,
          movement_type: 'purchase',
          quantity: 3,
          stock_delta: 3,
          stock_flow: 'Previous stock 0 · Received 3 · New stock 3',
          created_at: '2026-10-06T10:00:00Z',
        },
      ],
    });

    render(
      <StockHistoryModal
        embedded
        product={{
          id: 12,
          name: 'Shirt',
          has_variants: true,
          variants: [
            { id: 21, sku: 'S-RED', size: { name: 'S' }, color: { name: 'Red' }, stock_quantity: 3 },
            { id: 22, sku: 'M-BLUE', size: { name: 'M' }, color: { name: 'Blue' }, stock_quantity: 5 },
          ],
        }}
      />
    );

    expect(screen.getByTestId('stock-history-variant-picker')).toBeInTheDocument();
    expect(screen.getByText(/Choose a variant above/i)).toBeInTheDocument();
    expect(inventoryAPI.productHistory).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('Variant'), { target: { value: '21' } });

    await waitFor(() =>
      expect(screen.getByText(/Previous stock 0 · Received 3 · New stock 3/)).toBeInTheDocument()
    );
    expect(inventoryAPI.productHistory).toHaveBeenCalledWith(
      12,
      expect.objectContaining({ variant_id: '21', page: 1, page_size: 50 }),
    );
  });
});
