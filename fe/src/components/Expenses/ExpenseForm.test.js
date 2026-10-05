import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import ExpenseForm from './ExpenseForm';
import { expensesAPI, storeSettingsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { cacheStoreSettings } from '../../utils/storeSettingsCache';

jest.mock('../../services/api', () => ({
  expensesAPI: {
    update: jest.fn(),
    create: jest.fn(),
    categories: { list: jest.fn(), create: jest.fn() },
  },
  storeSettingsAPI: { get: jest.fn() },
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn(), info: jest.fn() },
}));

const categories = [{ id: 3, name: 'Fuel' }];
const expense = {
  id: 29,
  category: 3,
  amount: '300.00',
  description: 'Fuel',
  payment_method: 'cash',
  expense_date: '2026-10-05',
  status: 'pending',
};

function rejectWith(data) {
  expensesAPI.update.mockRejectedValue({ response: { status: 400, data } });
}

async function submit() {
  fireEvent.click(screen.getByRole('button', { name: 'Update' }));
  fireEvent.click(await screen.findByRole('button', { name: /confirm & update|submit for approval/i }));
}

describe('ExpenseForm save errors', () => {
  beforeEach(() => {
    localStorage.clear();
    storeSettingsAPI.get.mockResolvedValue({ data: { maker_checker_enabled: true } });
  });

  it('shows the server reason when the expense is locked', async () => {
    cacheStoreSettings({ maker_checker_enabled: false });
    rejectWith(['Approved records cannot be edited when maker-checker is enabled.']);
    render(<ExpenseForm expense={expense} categories={categories} onClose={jest.fn()} onSave={jest.fn()} />);
    await submit();
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        'Approved records cannot be edited when maker-checker is enabled.'
      )
    );
  });

  it('asks for a reason when the server needs one the form did not show', async () => {
    cacheStoreSettings({ maker_checker_enabled: false });
    rejectWith({ proposal_reason: ['A reason is required when maker-checker is enabled.'] });
    render(<ExpenseForm expense={expense} categories={categories} onClose={jest.fn()} onSave={jest.fn()} />);
    expect(screen.queryByLabelText(/reason/i)).not.toBeInTheDocument();
    await submit();
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('A reason is required when maker-checker is enabled.')
    );
    expect(storeSettingsAPI.get).toHaveBeenCalled();
    expect(document.getElementById('change_reason')).toBeInTheDocument();
  });

  it('sends the typed reason with the update', async () => {
    cacheStoreSettings({ maker_checker_enabled: true });
    expensesAPI.update.mockResolvedValue({ data: {} });
    const onSave = jest.fn();
    render(<ExpenseForm expense={expense} categories={categories} onClose={jest.fn()} onSave={onSave} />);
    fireEvent.change(document.getElementById('change_reason'), { target: { value: 'Fix amount' } });
    await submit();
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(expensesAPI.update).toHaveBeenCalledWith(
      29,
      expect.objectContaining({ proposal_reason: 'Fix amount' })
    );
  });

  it('never lets the form set an approval status', async () => {
    cacheStoreSettings({ maker_checker_enabled: false });
    expensesAPI.update.mockResolvedValue({ data: {} });
    const onSave = jest.fn();
    render(
      <ExpenseForm
        expense={{ ...expense, status: 'rejected' }}
        categories={categories}
        onClose={jest.fn()}
        onSave={onSave}
      />
    );
    expect(screen.queryByText('Status')).not.toBeInTheDocument();
    await submit();
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(expensesAPI.update.mock.calls[0][1]).not.toHaveProperty('status');
  });
});
