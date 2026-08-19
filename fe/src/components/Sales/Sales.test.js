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
  isManagerOrAdminFromStorage: () => true,
}));

jest.mock('../../utils/saleRefund', () => ({
  userCanRefundSales: () => false,
  saleIsRefundable: () => false,
  handleSaleRefundResponse: jest.fn(),
}));

jest.mock('../../services/api', () => ({
  salesAPI: {
    list: jest.fn(),
    get: jest.fn(),
    refund: jest.fn(),
  },
  reportsAPI: {
    exportFile: jest.fn(),
  },
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
});
