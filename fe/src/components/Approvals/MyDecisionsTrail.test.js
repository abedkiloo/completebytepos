import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import MyDecisionsTrail from './MyDecisionsTrail';
import { expensesAPI, pendingChangesAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  pendingChangesAPI: {
    myDecisions: jest.fn(),
    decisionPeople: jest.fn(),
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
  FilterBar: ({ children }) => <div data-testid="decisions-filters">{children}</div>,
  FilterField: ({ label, children }) => (
    <label>
      {label}
      {children}
    </label>
  ),
}));

jest.mock('../Shared/SearchableSelect', () => {
  return function MockSearchableSelect({ value, onChange, options = [], placeholder }) {
    return (
      <select
        aria-label={placeholder || 'select'}
        value={value || ''}
        onChange={(e) => onChange({ target: { value: e.target.value } })}
      >
        {options.map((o) => (
          <option key={o.id === '' ? 'any' : o.id} value={o.id}>
            {o.name}
          </option>
        ))}
      </select>
    );
  };
});

describe('MyDecisionsTrail', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    pendingChangesAPI.decisionPeople.mockResolvedValue({
      data: {
        requesters: [{ id: 3, name: 'cashier1' }],
        checkers: [{ id: 7, name: 'manager1' }],
      },
    });
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
            checked_by_username: 'manager1',
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
            checked_by_username: 'manager1',
            checked_at: '2026-10-07T08:00:00Z',
            original_values: {},
            proposed_values: {},
          },
        ],
      },
    });
    expensesAPI.list.mockResolvedValue({ data: { count: 0, results: [] } });
  });

  it('shows decisions with time, people, and comments', async () => {
    render(<MyDecisionsTrail includeExpenses />);

    expect(await screen.findByText('Zipper')).toBeInTheDocument();
    expect(screen.getByText('S-22')).toBeInTheDocument();
    expect(screen.getByText(/Seasonal price/)).toBeInTheDocument();
    expect(screen.getByText(/Missing receipt/)).toBeInTheDocument();
    expect(screen.getAllByText(/Decided by manager1/).length).toBeGreaterThan(0);
    expect(screen.getByTestId('my-decisions-trail')).toBeInTheDocument();
    expect(screen.getByTestId('decisions-pagination')).toHaveAttribute('data-count', '2');
    expect(pendingChangesAPI.myDecisions).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: expect.any(Number), scope: 'all' })
    );
  });

  it('opens detail dialog with requester reason and reject comment', async () => {
    render(<MyDecisionsTrail />);

    await screen.findByText('S-22');
    fireEvent.click(screen.getByText('S-22'));

    expect(await screen.findByText('Checker comment on reject')).toBeInTheDocument();
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
            checked_by_username: 'manager1',
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
        expect.objectContaining({ status: 'approved', page: 1, scope: 'all' })
      );
    });
    expect(await screen.findByText('Zipper')).toBeInTheDocument();
  });

  it('passes date and people filters to the API', async () => {
    render(<MyDecisionsTrail />);
    await screen.findByText('Zipper');

    fireEvent.change(screen.getByTestId('decisions-date-from'), {
      target: { value: '2026-10-01' },
    });
    fireEvent.change(screen.getByTestId('decisions-date-to'), {
      target: { value: '2026-10-07' },
    });

    await waitFor(() => {
      expect(pendingChangesAPI.myDecisions).toHaveBeenCalledWith(
        expect.objectContaining({
          date_from: '2026-10-01',
          date_to: '2026-10-07',
          scope: 'all',
        })
      );
    });

    fireEvent.change(screen.getByLabelText(/Requested by/), {
      target: { value: '3' },
    });

    await waitFor(() => {
      expect(pendingChangesAPI.myDecisions).toHaveBeenCalledWith(
        expect.objectContaining({ made_by: '3' })
      );
    });

    fireEvent.change(screen.getByLabelText(/Decided by/), {
      target: { value: '7' },
    });

    await waitFor(() => {
      expect(pendingChangesAPI.myDecisions).toHaveBeenCalledWith(
        expect.objectContaining({ checked_by: '7' })
      );
    });
  });
});

