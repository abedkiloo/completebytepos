import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import SaleApprovalsPage from './SaleApprovalsPage';
import { pendingChangesAPI, salesAPI } from '../../services/api';
import { toast } from '../../utils/toast';

jest.mock('react-router-dom', () => ({
  Navigate: () => null,
}));

let mockProfile = { role: 'manager', custom_role: { name: 'Manager' } };

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: () => ({
    user: {},
    profile: mockProfile,
    permissions: [{ module: 'sales', action: 'approve' }],
  }),
  hasPermission: (permissions, module, action) =>
    (permissions || []).some(
      (permission) => permission.module === module && permission.action === action
    ),
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn() },
}));

jest.mock('../../utils/navBadges', () => ({
  dispatchNavBadgesRefresh: jest.fn(),
}));

jest.mock('../Shared/HelpHint', () => () => null);

jest.mock('../../services/api', () => ({
  salesAPI: {
    list: jest.fn(),
    complete: jest.fn(),
    rejectComplete: jest.fn(),
  },
  pendingChangesAPI: {
    pending: jest.fn(),
    approve: jest.fn(),
    reject: jest.fn(),
  },
}));

function waitingSale(occurredAt) {
  return {
    id: 42,
    sale_number: 'S-2300',
    total: 2300,
    status: 'pending_approval',
    cashier_name: 'Ann',
    occurred_at: occurredAt,
    amount_paid: 2300,
    items: [{ quantity: 1 }],
    customer_name: 'Jane',
  };
}

function daysAgoIso(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString();
}

describe('SaleApprovalsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockProfile = { role: 'manager', custom_role: { name: 'Manager' } };
    salesAPI.list.mockResolvedValue({
      data: { results: [waitingSale(new Date().toISOString())] },
    });
    pendingChangesAPI.pending.mockResolvedValue({ data: [] });
    salesAPI.complete.mockResolvedValue({
      data: { id: 42, status: 'completed' },
    });
  });

  test('approves a waiting sale via POST /sales/:id/complete/', async () => {
    render(<SaleApprovalsPage />);
    expect(await screen.findByText('S-2300')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Approve/i }));
    await waitFor(() => expect(salesAPI.complete).toHaveBeenCalledWith(42));
    expect(toast.success).toHaveBeenCalledWith(
      expect.stringMatching(/S-2300 approved/i)
    );
  });

  test('shows the API error when approve fails', async () => {
    salesAPI.complete.mockRejectedValue({
      response: { data: { error: 'This sale is not waiting for approval.' } },
    });
    render(<SaleApprovalsPage />);
    fireEvent.click(await screen.findByRole('button', { name: /Approve/i }));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('This sale is not waiting for approval.')
    );
  });

  test('leaves a past-dated sale for an admin when signed in as manager', async () => {
    salesAPI.list.mockResolvedValue({ data: { results: [waitingSale(daysAgoIso(2))] } });
    render(<SaleApprovalsPage />);
    expect(await screen.findByTestId('past-dated-notice')).toHaveTextContent(
      /Only an admin can approve/i
    );
    expect(screen.queryByRole('button', { name: /Approve/i })).not.toBeInTheDocument();
  });

  test('admin can approve a past-dated sale', async () => {
    mockProfile = { role: 'super_admin', custom_role: { name: 'Super Admin' } };
    salesAPI.list.mockResolvedValue({ data: { results: [waitingSale(daysAgoIso(2))] } });
    render(<SaleApprovalsPage />);
    fireEvent.click(await screen.findByRole('button', { name: /Approve/i }));
    await waitFor(() => expect(salesAPI.complete).toHaveBeenCalledWith(42));
  });
});
