import { fireEvent, render, screen, waitFor } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  MemoryRouter: ({ children }) => children,
  Link: ({ children }) => children,
  useSearchParams: () => [new URLSearchParams(), jest.fn()],
}));

import { MemoryRouter } from 'react-router-dom';
import Expenses from './Expenses';
import { expensesAPI } from '../../services/api';
import { toast } from '../../utils/toast';

jest.mock('../../services/api', () => ({
  expensesAPI: {
    list: jest.fn(),
    statistics: jest.fn(),
    resubmit: jest.fn(),
    categories: { list: jest.fn() },
  },
  storeSettingsAPI: { get: jest.fn() },
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn(), info: jest.fn() },
}));

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem(
    'permissions',
    JSON.stringify([
      { module: 'expenses', action: 'view' },
      { module: 'expenses', action: 'create' },
    ])
  );
  localStorage.setItem('user', JSON.stringify({ id: 9, username: 'mgr' }));
  expensesAPI.list.mockResolvedValue({
    data: {
      count: 1,
      results: [
        {
          id: 44,
          expense_number: 'EXP-44',
          description: 'Returned fuel',
          amount: '300.00',
          status: 'rejected',
          category: 3,
          category_name: 'Fuel',
          payment_method: 'cash',
          expense_date: '2026-10-05',
          created_by: 9,
          created_by_name: 'mgr',
          is_claim: false,
        },
      ],
    },
  });
  expensesAPI.statistics.mockResolvedValue({
    data: { total_amount: 0, expense_count: 0, posted_total: 0 },
  });
  expensesAPI.categories.list.mockResolvedValue({ data: [{ id: 3, name: 'Fuel' }] });
  expensesAPI.resubmit.mockResolvedValue({ data: { id: 44, status: 'pending' } });
});

test('owner can edit and resubmit a rejected expense', async () => {
  render(
    <MemoryRouter>
      <Expenses />
    </MemoryRouter>
  );
  expect(await screen.findByLabelText('Edit expense')).toBeInTheDocument();
  expect(screen.getByTestId('expense-resubmit-44')).toBeInTheDocument();
  fireEvent.click(screen.getByTestId('expense-resubmit-44'));
  await waitFor(() => expect(expensesAPI.resubmit).toHaveBeenCalledWith(44));
  expect(toast.success).toHaveBeenCalledWith('Sent back for approval.');
});

test('claim-only owner can edit their rejected claim', async () => {
  localStorage.setItem(
    'permissions',
    JSON.stringify([{ module: 'expenses', action: 'claim' }])
  );
  localStorage.setItem('user', JSON.stringify({ id: 4, username: 'ann' }));
  expensesAPI.list.mockResolvedValue({
    data: {
      count: 1,
      results: [
        {
          id: 50,
          expense_number: 'EXP-50',
          description: 'Matatu',
          amount: '100.00',
          status: 'rejected',
          is_claim: true,
          created_by: 4,
          created_by_name: 'ann',
          expense_date: '2026-10-05',
          payment_method: 'cash',
        },
      ],
    },
  });
  render(
    <MemoryRouter>
      <Expenses />
    </MemoryRouter>
  );
  expect(await screen.findByLabelText('Edit expense')).toBeInTheDocument();
  expect(screen.getByTestId('expense-resubmit-50')).toBeInTheDocument();
});
