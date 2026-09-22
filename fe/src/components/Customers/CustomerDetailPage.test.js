import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { customersAPI, salesAPI } from '../../services/api';

const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({ customerId: '7' }),
  useSearchParams: () => [new URLSearchParams(), jest.fn()],
  Link: ({ to, children, ...props }) => (
    <a href={typeof to === 'string' ? to : '#'} {...props}>
      {children}
    </a>
  ),
}));

jest.mock('../../services/api', () => ({
  customersAPI: {
    detail: jest.fn(),
  },
  salesAPI: {
    get: jest.fn(),
    refund: jest.fn(),
    rollback: jest.fn(),
  },
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: () => ({
    permissions: [
      { module: 'customers', action: 'view', name: 'customers.view' },
      { module: 'customers', action: 'update', name: 'customers.update' },
    ],
  }),
  hasPermission: () => true,
  isManagerOrAdminFromStorage: () => true,
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn() },
}));

jest.mock('../../utils/navBadges', () => ({
  dispatchNavBadgesRefresh: jest.fn(),
}));

jest.mock('../../utils/saleRefund', () => ({
  userCanRefundSales: () => true,
  userCanRollbackSales: () => false,
  handleSaleRefundResponse: jest.fn(),
}));

jest.mock('./ReceiveWalletPaymentDialog', () => () => null);
jest.mock('../Sales/SaleDetailDialog', () => () => null);
jest.mock('../Sales/RefundSaleDialog', () => () => null);
jest.mock('../Sales/SaleRollbackDialog', () => () => null);

jest.mock('lucide-react', () => {
  const React = require('react');
  const Icon = () => React.createElement('span');
  return new Proxy(
    {},
    {
      get: () => Icon,
    }
  );
});

jest.mock('../page', () => ({
  PageShell: ({ children }) => <div>{children}</div>,
  PageHeader: ({ title, children }) => (
    <header>
      <h1>{title}</h1>
      {children}
    </header>
  ),
  PageLoading: () => <div>Loading…</div>,
  EmptyState: ({ title }) => <div>{title}</div>,
  SummaryCard: ({ label, value }) => (
    <div>
      <span>{label}</span>
      <span>{value}</span>
    </div>
  ),
  DataTable: ({ children }) => <table>{children}</table>,
  DataTableHeader: ({ children }) => (
    <thead>
      <tr>{children}</tr>
    </thead>
  ),
  DataTableHead: ({ children }) => <th>{children}</th>,
  DataTableBody: ({ children }) => <tbody>{children}</tbody>,
  DataTableRow: ({ children, onClick }) => (
    <tr onClick={onClick}>{children}</tr>
  ),
  DataTableCell: ({ children }) => <td>{children}</td>,
  ListPaginationRail: ({ children }) => <div>{children}</div>,
}));

jest.mock('../ui/button', () => ({
  Button: ({ children, onClick, asChild, ...rest }) =>
    asChild ? <>{children}</> : (
      <button type="button" onClick={onClick} {...rest}>
        {children}
      </button>
    ),
}));

jest.mock('../ui/badge', () => ({
  Badge: ({ children }) => <span>{children}</span>,
}));

jest.mock('./CustomerWalletBalance', () => ({
  CustomerWalletBalance: () => <div data-testid="wallet-balance" />,
}));

import CustomerDetailPage from './CustomerDetailPage';

const DETAIL = {
  customer: {
    id: 7,
    name: 'Jane Doe',
    phone: '0712345678',
    email: 'jane@example.com',
    customer_code: 'C-7',
    wallet_balance: '-300.00',
    wallet_debt: '300.00',
    wallet_credit: '0.00',
    total_outstanding: '0.00',
    standing: 'debt',
    is_active: true,
  },
  standing_summary: {
    standing: 'debt',
    wallet_debt: '300.00',
    wallet_credit: '0.00',
    total_outstanding: '0.00',
    lifetime_orders: 1,
    lifetime_sales_total: '630.00',
    total_debt_incurred: '600.00',
    total_debt_collected: '300.00',
  },
  orders: [
    {
      id: 11,
      sale_number: 'SALE-11',
      occurred_at: '2026-09-10T12:00:00Z',
      total: '630.00',
      paid_amount: '330.00',
      debt_amount: '300.00',
      payment_status: 'partial',
    },
  ],
  orders_pagination: { count: 1, page: 1, page_size: 25 },
  ledger: [
    {
      id: 2,
      source_type: 'debt_settlement',
      amount: '300.00',
      balance_after: '-300.00',
      previous_debt: '600.00',
      payment_amount: '300.00',
      new_debt: '300.00',
      created_at: '2026-09-11T09:00:00Z',
    },
  ],
  ledger_pagination: { count: 1, page: 1, page_size: 50 },
};

describe('CustomerDetailPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    customersAPI.detail.mockResolvedValue({ data: DETAIL });
  });

  it('loads profile, orders, and debt KPIs', async () => {
    render(<CustomerDetailPage />);

    expect(await screen.findByRole('heading', { name: 'Jane Doe' })).toBeInTheDocument();
    expect(customersAPI.detail).toHaveBeenCalledWith('7', expect.any(Object));
    expect(screen.getByText('SALE-11')).toBeInTheDocument();
    expect(screen.getByText(/Wallet debt/i)).toBeInTheDocument();
    expect(screen.getByText(/Lifetime sales/i)).toBeInTheDocument();
  });

  it('opens sale detail when an order row is clicked', async () => {
    salesAPI.get.mockResolvedValue({ data: { id: 11, sale_number: 'SALE-11' } });
    render(<CustomerDetailPage />);
    await screen.findByText('SALE-11');
    fireEvent.click(screen.getByText('SALE-11'));
    await waitFor(() => {
      expect(salesAPI.get).toHaveBeenCalledWith(11);
    });
  });

  it('shows not-found empty state when API fails', async () => {
    customersAPI.detail.mockRejectedValue({ response: { data: { error: 'missing' } } });
    render(<CustomerDetailPage />);
    expect(await screen.findByText(/Customer not found/i)).toBeInTheDocument();
  });
});
