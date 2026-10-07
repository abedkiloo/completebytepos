import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import MyDecisionsTrail from './MyDecisionsTrail';
import { expensesAPI, pendingChangesAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  pendingChangesAPI: {
    myDecisions: jest.fn(),
  },
  expensesAPI: {
    list: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: () => ({ user: { id: 7 }, permissions: [] }),
}));

jest.mock('../page', () => ({
  PageLoading: () => <div>Loading…</div>,
  ListPaginationRail: ({ children, totalCount, suffix }) => (
    <div data-testid="decisions-pagination" data-count={totalCount} data-suffix={suffix}>
      {children}
    </div>
  ),
}));

describe('MyDecisionsTrail', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    pendingChangesAPI.myDecisions.mockResolvedValue({
      data: {
        count: 2,
        results: [
          {
            id: 1,
            action_type: 'product_price',
            entity_type: 'products.Product',
            entity_repr: 'Zipper',
            status: 'approved',
            reason: 'Seasonal price',
            rejection_reason: '',
            made_by_username: 'cashier1',
            checked_at: '2026-10-07T09:00:00Z',
            original_values: { price: '20' },
            proposed_values: { price: '25' },
          },
          {
            id: 2,
            action_type: 'sale_refund',
            entity_type: 'sales.Sale',
            entity_repr: 'S-22',
            status: 'rejected',
            reason: 'Customer return',
            rejection_reason: 'Missing receipt',
            made_by_username: 'cashier2',
            checked_at: '2026-10-07T08:00:00Z',
            original_values: {},
            proposed_values: {},
          },
        ],
      },
    });
    expensesAPI.list.mockResolvedValue({ data: { count: 0, results: [] } });
  });

  it('shows decisions with time and comments', async () => {
    render(<MyDecisionsTrail includeExpenses />);

    expect(await screen.findByText('Zipper')).toBeInTheDocument();
    expect(screen.getByText('S-22')).toBeInTheDocument();
    expect(screen.getByText(/Seasonal price/)).toBeInTheDocument();
    expect(screen.getByText(/Missing receipt/)).toBeInTheDocument();
    expect(screen.getAllByText(/You decided/).length).toBeGreaterThan(0);
    expect(screen.getByTestId('my-decisions-trail')).toBeInTheDocument();
    expect(screen.getByTestId('decisions-pagination')).toHaveAttribute('data-count', '2');
    expect(pendingChangesAPI.myDecisions).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: expect.any(Number) })
    );
  });

  it('opens detail dialog with requester reason and reject comment', async () => {
    render(<MyDecisionsTrail />);

    await screen.findByText('S-22');
    fireEvent.click(screen.getByText('S-22'));

    expect(await screen.findByText('Your comment on reject')).toBeInTheDocument();
    expect(screen.getAllByText('Missing receipt').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Customer return').length).toBeGreaterThan(0);
  });

  it('filters to approved only', async () => {
    render(<MyDecisionsTrail />);
    await screen.findByText('Zipper');

    pendingChangesAPI.myDecisions.mockResolvedValueOnce({
      data: {
        count: 1,
        results: [
          {
            id: 1,
            action_type: 'product_price',
            entity_type: 'products.Product',
            entity_repr: 'Zipper',
            status: 'approved',
            reason: 'Seasonal price',
            made_by_username: 'cashier1',
            checked_at: '2026-10-07T09:00:00Z',
            original_values: {},
            proposed_values: {},
          },
        ],
      },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Approved' }));

    await waitFor(() => {
      expect(pendingChangesAPI.myDecisions).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'approved', page: 1 })
      );
    });
    expect(await screen.findByText('Zipper')).toBeInTheDocument();
  });
});
