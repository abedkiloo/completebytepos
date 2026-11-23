import { fireEvent, render, screen, waitFor } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  MemoryRouter: ({ children }) => children,
  Link: ({ children }) => children,
  useSearchParams: () => [new URLSearchParams(), jest.fn()],
}));

import { MemoryRouter } from 'react-router-dom';
import Expenses from './Expenses';
import { expensesAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  expensesAPI: {
    list: jest.fn(),
    statistics: jest.fn(),
    claim: jest.fn(),
    decideClaim: jest.fn(),
    categories: { list: jest.fn() },
  },
  storeSettingsAPI: { get: jest.fn() },
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn(), info: jest.fn() },
}));

function asStaff() {
  localStorage.setItem('permissions', JSON.stringify([
    { module: 'expenses', action: 'claim' },
  ]));
  localStorage.setItem('user', JSON.stringify({ id: 4, username: 'ann' }));
}

function asManager() {
  localStorage.setItem('permissions', JSON.stringify([
    { module: 'expenses', action: 'view' },
    { module: 'expenses', action: 'claim_approve' },
  ]));
  localStorage.setItem('user', JSON.stringify({ id: 3, username: 'mo' }));
}

beforeEach(() => {
  localStorage.clear();
  expensesAPI.list.mockResolvedValue({ data: { results: [], count: 0 } });
  expensesAPI.statistics.mockResolvedValue({ data: { total_amount: 0, expense_count: 0, posted_total: 0 } });
  expensesAPI.categories.list.mockResolvedValue({ data: [] });
  expensesAPI.claim.mockResolvedValue({ data: { id: 9, is_claim: true, status: 'pending' } });
  expensesAPI.decideClaim.mockResolvedValue({ data: { id: 9, status: 'approved', is_claim: true } });
});

test('an employee sends a claim and does not see another phone', async () => {
  asStaff();
  render(<MemoryRouter><Expenses /></MemoryRouter>);
  fireEvent.click(await screen.findByTestId('expense-claim'));
  fireEvent.change(screen.getByTestId('expense-claim-amount'), { target: { value: '250.00' } });
  fireEvent.change(screen.getByTestId('expense-claim-description'), { target: { value: 'Matatu fare' } });
  fireEvent.click(screen.getByTestId('expense-claim-send'));
  await waitFor(() => expect(expensesAPI.claim).toHaveBeenCalledWith(expect.objectContaining({
    amount: '250.00',
    description: 'Matatu fare',
  })));
  expect(JSON.stringify(expensesAPI.claim.mock.calls)).not.toContain('0711');
  expect(expensesAPI.statistics).not.toHaveBeenCalled();
});

test('a manager approves a claim that is not theirs', async () => {
  asManager();
  expensesAPI.list.mockResolvedValue({
    data: {
      count: 1,
      results: [{
        id: 9,
        expense_number: 'EXP-1',
        description: 'Matatu fare',
        amount: '250.00',
        status: 'pending',
        is_claim: true,
        created_by: 4,
        created_by_name: 'ann',
        expense_date: '2026-11-23',
        category_include_in_trading_profit: true,
        notes: '',
      }],
    },
  });
  render(<MemoryRouter><Expenses /></MemoryRouter>);
  fireEvent.click(await screen.findByTestId('claim-approve-9'));
  await waitFor(() => expect(expensesAPI.decideClaim).toHaveBeenCalledWith(9, {
    decision: 'approved',
    rejection_reason: '',
  }));
  expect(screen.queryByText('0711555019')).not.toBeInTheDocument();
});
