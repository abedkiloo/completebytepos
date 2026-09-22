/**
 * Customer day drill-down from Daily Sales Tracker.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

const mockNavigate = jest.fn();
let mockParams = { customerId: '5' };
let mockSearchParams = new URLSearchParams('date=2026-09-12');
const mockSetSearchParams = jest.fn((updater) => {
  if (typeof updater === 'function') {
    mockSearchParams = updater(mockSearchParams);
  }
});

jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useParams: () => mockParams,
  useSearchParams: () => [mockSearchParams, mockSetSearchParams],
  Link: ({ to, children, ...props }) => (
    <a href={typeof to === 'string' ? to : '#'} {...props}>
      {children}
    </a>
  ),
}));

jest.mock('../../services/api', () => ({
  salesAPI: {
    dailyCustomer: jest.fn(),
    get: jest.fn(),
    refund: jest.fn(),
    rollback: jest.fn(),
  },
}));

jest.mock('../../utils/dailySalesAccess', () => ({
  canViewDailySalesFromStorage: jest.fn(() => true),
  dailySalesListPath: (date) => (date ? `/sales/daily?date=${date}` : '/sales/daily'),
  dayStandingLabel: (s) => (s === 'debt' ? 'Taken on debt' : s === 'mixed' ? 'Mixed — some debt' : 'Good standing'),
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: () => ({
    permissions: [
      { module: 'sales', action: 'daily_sales' },
      { module: 'customers', action: 'update' },
    ],
  }),
  hasPermission: () => true,
  isManagerOrAdminFromStorage: () => true,
}));

jest.mock('../../utils/saleRefund', () => ({
  userCanRefundSales: () => true,
  userCanRollbackSales: () => false,
  handleSaleRefundResponse: () => ({ handled: true }),
}));

jest.mock('../../utils/navBadges', () => ({
  dispatchNavBadgesRefresh: jest.fn(),
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn() },
}));

jest.mock('lucide-react', () => {
  const React = require('react');
  const Icon = () => React.createElement('span');
  return {
    __esModule: true,
    ArrowLeft: Icon,
    CheckCircle2: Icon,
    Mail: Icon,
    MapPin: Icon,
    Phone: Icon,
    Receipt: Icon,
    TrendingDown: Icon,
    Users: Icon,
    Wallet: Icon,
  };
});

jest.mock('../ui/button', () => ({
  Button: ({ children, onClick, type = 'button', disabled }) => (
    <button type={type} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  ),
}));

jest.mock('../ui/input', () => ({
  Input: (props) => <input {...props} />,
}));

jest.mock('../ui/badge', () => ({
  Badge: ({ children }) => <span>{children}</span>,
}));

jest.mock('./SaleDetailDialog', () => ({
  __esModule: true,
  default: ({ open, sale }) =>
    open && sale ? <div data-testid="sale-detail-dialog">Receipt: {sale.sale_number}</div> : null,
}));
jest.mock('./RefundSaleDialog', () => () => null);
jest.mock('./SaleRollbackDialog', () => () => null);
jest.mock('../Customers/ReceiveWalletPaymentDialog', () => ({
  __esModule: true,
  default: ({ open, customer, onSuccess }) =>
    open && customer ? (
      <div data-testid="settle-dialog">
        <span>{customer.name}</span>
        <button type="button" onClick={() => onSuccess?.()}>
          Confirm settle
        </button>
      </div>
    ) : null,
}));

jest.mock('../page', () => ({
  __esModule: true,
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
  DataTableRow: ({ children }) => <tr>{children}</tr>,
  DataTableCell: ({ children }) => <td>{children}</td>,
}));

import { salesAPI } from '../../services/api';
import { canViewDailySalesFromStorage } from '../../utils/dailySalesAccess';
import CustomerDailyDetailPage from './CustomerDailyDetailPage';

const PAYLOAD = {
  date: '2026-09-12',
  customer: {
    id: 5,
    name: 'Bob Debtor',
    phone: '0711223344',
    email: 'bob@example.com',
    customer_code: 'CUST-005',
    customer_type: 'individual',
    city: 'Nairobi',
    address: '1 Main St',
    is_active: true,
    wallet_balance: '-2000.00',
    wallet_debt: '2000.00',
    wallet_credit: '0.00',
    standing: 'debt',
    total_outstanding: '0.00',
  },
  day_summary: {
    orders_count: 1,
    total_sales: '2500.00',
    total_paid: '500.00',
    total_debt_incurred: '2000.00',
    paid_orders_count: 0,
    debt_orders_count: 1,
    partial_orders_count: 1,
    debt_collected: '100.00',
    day_standing: 'mixed',
  },
  standing_summary: {
    standing: 'debt',
    wallet_debt: '2000.00',
    wallet_credit: '0.00',
    lifetime_orders: 4,
    lifetime_sales_total: '9000.00',
  },
  orders: [
    {
      id: 102,
      sale_number: 'SALE-PARTIAL-02',
      occurred_at: '2026-09-12T10:15:00Z',
      total: '2500.00',
      paid_amount: '500.00',
      debt_amount: '2000.00',
      payment_status: 'partial',
      payment_method: 'mpesa',
    },
  ],
};

describe('CustomerDailyDetailPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockParams = { customerId: '5' };
    mockSearchParams = new URLSearchParams('date=2026-09-12');
    canViewDailySalesFromStorage.mockReturnValue(true);
    salesAPI.dailyCustomer.mockResolvedValue({ data: PAYLOAD });
  });

  it('renders customer identity, day summaries, and orders', async () => {
    render(<CustomerDailyDetailPage />);
    expect(await screen.findByText('SALE-PARTIAL-02')).toBeInTheDocument();
    expect(screen.getAllByText('Bob Debtor').length).toBeGreaterThan(0);
    expect(screen.getByText('Has open debt')).toBeInTheDocument();
    expect(screen.getByText('Sales on this day')).toBeInTheDocument();
    expect(screen.getByText('Account overview')).toBeInTheDocument();
    expect(salesAPI.dailyCustomer).toHaveBeenCalledWith('5', { date: '2026-09-12' });
  });

  it('shows restricted empty state without permission', async () => {
    canViewDailySalesFromStorage.mockReturnValue(false);
    render(<CustomerDailyDetailPage />);
    expect(await screen.findByText(/Daily Sales is restricted/i)).toBeInTheDocument();
    expect(salesAPI.dailyCustomer).not.toHaveBeenCalled();
  });

  it('shows not-found when API returns empty customer', async () => {
    salesAPI.dailyCustomer.mockResolvedValueOnce({ data: { customer: null, orders: [] } });
    render(<CustomerDailyDetailPage />);
    expect(await screen.findByText(/Customer not found/i)).toBeInTheDocument();
  });

  it('opens settle dialog from Receive payment', async () => {
    render(<CustomerDailyDetailPage />);
    await screen.findByText('SALE-PARTIAL-02');
    fireEvent.click(screen.getByRole('button', { name: /Receive payment/i }));
    expect(await screen.findByTestId('settle-dialog')).toHaveTextContent('Bob Debtor');
  });

  it('opens receipt from order row', async () => {
    salesAPI.get.mockResolvedValueOnce({
      data: { id: 102, sale_number: 'SALE-PARTIAL-02' },
    });
    render(<CustomerDailyDetailPage />);
    await screen.findByText('SALE-PARTIAL-02');
    fireEvent.click(screen.getByRole('button', { name: /^Receipt$/i }));
    expect(await screen.findByTestId('sale-detail-dialog')).toHaveTextContent('SALE-PARTIAL-02');
  });

  it('hides receive payment when customer is in good standing', async () => {
    salesAPI.dailyCustomer.mockResolvedValueOnce({
      data: {
        ...PAYLOAD,
        customer: {
          ...PAYLOAD.customer,
          standing: 'good',
          wallet_debt: '0.00',
          wallet_credit: '10.00',
          wallet_balance: '10.00',
        },
      },
    });
    render(<CustomerDailyDetailPage />);
    await screen.findByText('SALE-PARTIAL-02');
    expect(screen.queryByRole('button', { name: /Receive payment/i })).not.toBeInTheDocument();
    expect(screen.getByText('Good standing')).toBeInTheDocument();
  });

  it('confirms settle and reloads', async () => {
    render(<CustomerDailyDetailPage />);
    await screen.findByText('SALE-PARTIAL-02');
    fireEvent.click(screen.getByRole('button', { name: /Receive payment/i }));
    fireEvent.click(screen.getByRole('button', { name: /Confirm settle/i }));
    await waitFor(() => {
      expect(salesAPI.dailyCustomer.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
  });

  it('shows empty orders state for quiet days', async () => {
    salesAPI.dailyCustomer.mockResolvedValueOnce({
      data: {
        ...PAYLOAD,
        day_summary: { ...PAYLOAD.day_summary, orders_count: 0, day_standing: 'good' },
        orders: [],
      },
    });
    render(<CustomerDailyDetailPage />);
    expect(await screen.findByText(/No sales for this customer on this day/i)).toBeInTheDocument();
  });

  it('handles API failure gracefully', async () => {
    const { toast } = require('../../utils/toast');
    salesAPI.dailyCustomer.mockRejectedValueOnce({
      response: { data: { error: 'Boom' } },
      message: 'Boom',
    });
    render(<CustomerDailyDetailPage />);
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalled();
    });
    expect(await screen.findByText(/Customer not found/i)).toBeInTheDocument();
  });

  it('changes date via previous day', async () => {
    render(<CustomerDailyDetailPage />);
    await screen.findByText('SALE-PARTIAL-02');
    fireEvent.click(screen.getByRole('button', { name: /Previous day/i }));
    await waitFor(() => {
      expect(mockSetSearchParams).toHaveBeenCalled();
    });
  });

  it('moves to next day when enabled', async () => {
    mockSearchParams = new URLSearchParams('date=2026-09-10');
    render(<CustomerDailyDetailPage />);
    await screen.findByText('SALE-PARTIAL-02');
    fireEvent.click(screen.getByRole('button', { name: /Next day/i }));
    await waitFor(() => {
      expect(mockSetSearchParams).toHaveBeenCalled();
    });
  });

  it('jumps to Today button', async () => {
    mockSearchParams = new URLSearchParams('date=2026-09-10');
    render(<CustomerDailyDetailPage />);
    await screen.findByText('SALE-PARTIAL-02');
    fireEvent.click(screen.getByRole('button', { name: /^Today$/i }));
    await waitFor(() => {
      expect(mockSetSearchParams).toHaveBeenCalled();
    });
  });
});
