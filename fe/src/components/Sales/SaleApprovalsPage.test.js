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

jest.mock('../ui/dialog', () => {
  const React = require('react');
  return {
    Dialog: ({ open, children }) => (open ? <div data-testid="approval-dialog">{children}</div> : null),
    DialogContent: ({ children }) => <div>{children}</div>,
    DialogHeader: ({ children }) => <div>{children}</div>,
    DialogFooter: ({ children }) => <div>{children}</div>,
    DialogTitle: ({ children }) => <h2>{children}</h2>,
    DialogDescription: ({ children }) => <p>{children}</p>,
  };
});

jest.mock('../../services/api', () => ({
  salesAPI: {
    list: jest.fn(),
    get: jest.fn(),
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

async function openSaleRow() {
  const row = await screen.findByTestId('sale-approval-list-row');
  fireEvent.click(row);
  expect(await screen.findByTestId('approval-dialog')).toBeInTheDocument();
}

describe('SaleApprovalsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockProfile = { role: 'manager', custom_role: { name: 'Manager' } };
    salesAPI.list.mockResolvedValue({
      data: { results: [waitingSale(new Date().toISOString())] },
    });
    salesAPI.get.mockImplementation(async (id) => ({
      data: {
        id,
        sale_number: 'S-2300',
        status: 'pending_approval',
        approval_details: {
          sections: [
            {
              title: 'Money',
              facts: [{ label: 'Total', value: '2300', kind: 'money' }],
            },
          ],
        },
      },
    }));
    pendingChangesAPI.pending.mockResolvedValue({ data: [] });
    salesAPI.complete.mockResolvedValue({
      data: { id: 42, status: 'completed' },
    });
  });

  test('lists sales as compact rows then approves from the popup', async () => {
    render(<SaleApprovalsPage />);
    expect(await screen.findByText('S-2300')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Approve/i })).not.toBeInTheDocument();
    await openSaleRow();
    fireEvent.click(screen.getByRole('button', { name: /Approve/i }));
    await waitFor(() => expect(salesAPI.complete).toHaveBeenCalledWith(42));
    expect(toast.success).toHaveBeenCalledWith(
      expect.stringMatching(/S-2300 approved/i)
    );
  });

  test('shows the items and money of the sale before approving', async () => {
    salesAPI.list.mockResolvedValue({
      data: {
        results: [
          {
            ...waitingSale(new Date().toISOString()),
            approval_details: {
              sections: [
                {
                  title: 'Items',
                  lines: [
                    { name: 'Red Shuka', variant: '', quantity: '2', unit_price: '1150.00', subtotal: '2300.00' },
                  ],
                },
                {
                  title: 'Money',
                  facts: [{ label: 'Payment method', value: 'M-PESA', kind: 'text' }],
                },
              ],
            },
          },
        ],
      },
    });
    render(<SaleApprovalsPage />);
    await openSaleRow();
    expect(await screen.findByText('Red Shuka')).toBeInTheDocument();
    expect(screen.getByText('M-PESA')).toBeInTheDocument();
    expect(screen.getByTestId('approval-details')).toBeInTheDocument();
    expect(salesAPI.get).not.toHaveBeenCalled();
  });

  test('loads sale detail when the list row has no approval breakdown', async () => {
    render(<SaleApprovalsPage />);
    await openSaleRow();
    await waitFor(() => expect(salesAPI.get).toHaveBeenCalledWith(42));
    expect(await screen.findByTestId('approval-details')).toBeInTheDocument();
    expect(screen.getByText('Total')).toBeInTheDocument();
  });

  test('shows the API error when approve fails', async () => {
    salesAPI.complete.mockRejectedValue({
      response: { data: { error: 'This sale is not waiting for approval.' } },
    });
    render(<SaleApprovalsPage />);
    await openSaleRow();
    fireEvent.click(screen.getByRole('button', { name: /Approve/i }));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('This sale is not waiting for approval.')
    );
  });

  test('leaves a past-dated sale for an admin when signed in as manager', async () => {
    salesAPI.list.mockResolvedValue({ data: { results: [waitingSale(daysAgoIso(2))] } });
    render(<SaleApprovalsPage />);
    await openSaleRow();
    expect(await screen.findByTestId('past-dated-notice')).toHaveTextContent(
      /Only an admin can approve/i
    );
    expect(screen.queryByRole('button', { name: /Approve/i })).not.toBeInTheDocument();
  });

  test('admin can approve a past-dated sale', async () => {
    mockProfile = { role: 'super_admin', custom_role: { name: 'Super Admin' } };
    salesAPI.list.mockResolvedValue({ data: { results: [waitingSale(daysAgoIso(2))] } });
    render(<SaleApprovalsPage />);
    await openSaleRow();
    fireEvent.click(screen.getByRole('button', { name: /Approve/i }));
    await waitFor(() => expect(salesAPI.complete).toHaveBeenCalledWith(42));
  });
});
