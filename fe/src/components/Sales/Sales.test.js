import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import Sales from './Sales';
import { reportsAPI, salesAPI } from '../../services/api';

jest.mock('react-router-dom', () => ({
  Link: ({ children, to, ...props }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: () => ({ permissions: [{ module: 'sales', action: 'refund' }] }),
  hasPermission: (permissions, module, action) =>
    permissions.some((permission) =>
      permission.module === module && permission.action === action
    ),
  isManagerOrAdminFromStorage: () => true,
  userSeesAllSalesFromStorage: () => mockSeesAllSales(),
}));

const mockSeesAllSales = jest.fn(() => false);

jest.mock('../../utils/saleRefund', () => ({
  userCanRefundSales: () => false,
  userCanRollbackSales: () => false,
  userCanUnvoidSales: () => false,
  saleIsRefundable: () => false,
  saleIsRollbackable: () => false,
  saleIsUnvoidable: () => false,
  handleSaleRefundResponse: jest.fn(),
}));

jest.mock('../../services/api', () => ({
  salesAPI: {
    list: jest.fn(),
    sellers: jest.fn(),
    historySummary: jest.fn(),
    get: jest.fn(),
    refund: jest.fn(),
    rollback: jest.fn(),
  },
  reportsAPI: {
    exportFile: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn(), info: jest.fn() },
}));

jest.mock('./RefundSaleDialog', () => () => null);
jest.mock('./SaleDetailDialog', () => () => null);

describe('Sales history export', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    salesAPI.list.mockResolvedValue({
      data: {
        count: 1,
        results: [
          {
            id: 1,
            sale_number: 'S-100',
            created_at: '2026-08-18T10:00:00Z',
            cashier_name: 'Ada',
            total: 150,
            payment_method: 'cash',
            status: 'completed',
            items: [{ quantity: 2 }],
          },
        ],
      },
    });
    reportsAPI.exportFile.mockResolvedValue('sales-history.pdf');
    salesAPI.sellers.mockResolvedValue({
      data: [
        { id: 7, username: 'ada', display_name: 'Ada Lovelace' },
        { id: 8, username: 'bob', display_name: 'Bob' },
      ],
    });
    mockSeesAllSales.mockReturnValue(false);
  });

  it('hides the Sold by filter from staff who only see their own sales', async () => {
    render(<Sales />);
    await waitFor(() => expect(screen.getByText('S-100')).toBeInTheDocument());
    expect(screen.queryByText('Sold by')).not.toBeInTheDocument();
    expect(salesAPI.sellers).not.toHaveBeenCalled();
  });

  it('lets admins and managers filter history by seller', async () => {
    mockSeesAllSales.mockReturnValue(true);
    render(<Sales />);
    await waitFor(() => expect(screen.getByText('S-100')).toBeInTheDocument());
    expect(screen.getByText('Sold by')).toBeInTheDocument();
    await waitFor(() => {
      expect(document.querySelector('select[name="cashier_id"] option[value="8"]')).not.toBeNull();
    });

    fireEvent.change(document.querySelector('select[name="cashier_id"]'), {
      target: { name: 'cashier_id', value: '8' },
    });

    await waitFor(() => {
      expect(salesAPI.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ cashier_id: '8' })
      );
    });
  });

  it('shows PDF and Excel downloads and uses the current filters', async () => {
    render(<Sales />);

    await waitFor(() => {
      expect(screen.getByText('S-100')).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /Download PDF/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download Excel/i })).toBeInTheDocument();

    fireEvent.change(document.querySelector('input[name="date_from"]'), {
      target: { name: 'date_from', value: '2026-08-01' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Download PDF/i }));

    await waitFor(() => {
      expect(reportsAPI.exportFile).toHaveBeenCalledWith(
        'sales-history',
        { date_from: '2026-08-01' },
        'pdf'
      );
    });
  });

  it('hides Show total from staff who only see their own sales', async () => {
    render(<Sales />);
    await waitFor(() => expect(screen.getByText('S-100')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /Show total for selected range/i })).not.toBeInTheDocument();
  });

  it('lets managers calculate the selected period total on click', async () => {
    mockSeesAllSales.mockReturnValue(true);
    salesAPI.historySummary.mockResolvedValue({
      data: {
        count: 2,
        total_amount: '350.00',
        by_method: [
          { payment_method: 'cash', payment_method_label: 'Cash', count: 1, total: '100.00' },
          { payment_method: 'mpesa', payment_method_label: 'M-PESA', count: 1, total: '250.00' },
        ],
        date_from: '2026-08-01',
        date_to: '2026-08-18',
      },
    });

    render(<Sales />);
    await waitFor(() => expect(screen.getByText('S-100')).toBeInTheDocument());

    fireEvent.change(document.querySelector('input[name="date_from"]'), {
      target: { name: 'date_from', value: '2026-08-01' },
    });
    fireEvent.change(document.querySelector('input[name="date_to"]'), {
      target: { name: 'date_to', value: '2026-08-18' },
    });

    await waitFor(() => {
      expect(salesAPI.list).toHaveBeenCalledWith(
        expect.objectContaining({
          date_from: '2026-08-01',
          date_to: '2026-08-18',
        })
      );
    });

    fireEvent.click(screen.getByRole('button', { name: /Show total for selected range/i }));

    await waitFor(() => {
      expect(salesAPI.historySummary).toHaveBeenCalledWith(
        expect.objectContaining({
          date_from: '2026-08-01',
          date_to: '2026-08-18',
          status: 'completed',
        })
      );
    });
    await waitFor(() => {
      expect(screen.getByText('Range total')).toBeInTheDocument();
    });
  });
});
